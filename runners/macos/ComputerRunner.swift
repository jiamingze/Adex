import AppKit
import ApplicationServices
import CryptoKit
import ScreenCaptureKit
import Vision

// The child must stop even if its Tools parent crashes; keep this deadline shorter
// than the PG host-command lease so an orphan cannot overlap a successor command.
DispatchQueue.global().asyncAfter(deadline: .now() + 15) { exit(124) }

func respond(_ object: [String: Any]) {
  let data = try! JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
  FileHandle.standardOutput.write(data)
}
func attribute(_ element: AXUIElement, _ name: String) -> AnyObject? {
  var value: CFTypeRef?
  guard AXUIElementCopyAttributeValue(element, name as CFString, &value) == .success else {
    return nil
  }
  return value
}
func text(_ element: AXUIElement, _ name: String) -> String {
  attribute(element, name) as? String ?? ""
}
func tree(_ root: AXUIElement) -> ([[String: Any]], [String: AXUIElement]) {
  var nodes = [[String: Any]]()
  var elements = [String: AXUIElement]()
  var valueBudget = 16000
  func walk(_ element: AXUIElement, _ path: String, _ depth: Int) {
    guard nodes.count < 600, depth < 28 else { return }
    let role = text(element, kAXRoleAttribute)
    let secure =
      text(element, kAXSubroleAttribute) == "AXSecureTextField" || role == "AXSecureTextField"
    var names: CFArray?
    AXUIElementCopyActionNames(element, &names)
    var settable = DarwinBoolean(false)
    AXUIElementIsAttributeSettable(element, kAXValueAttribute as CFString, &settable)
    let rawValue = secure ? "" : text(element, kAXValueAttribute)
    let value = String(rawValue.prefix(min(1500, max(0, valueBudget))))
    valueBudget -= value.count
    nodes.append([
      "id": path, "role": role,
      "title": secure
        ? "[secure]"
        : String(
          (text(element, kAXTitleAttribute).isEmpty
            ? text(element, kAXDescriptionAttribute) : text(element, kAXTitleAttribute)).prefix(300)
        ),
      "identifier": secure ? "" : text(element, kAXIdentifierAttribute),
      "placeholder": secure ? "" : String(text(element, "AXPlaceholderValue").prefix(200)),
      "help": secure ? "" : String(text(element, kAXHelpAttribute).prefix(200)),
      "url": secure ? "" : ((attribute(element, "AXURL") as? URL)?.absoluteString ?? ""),
      "value": secure ? "[redacted]" : value,
      "truncated": rawValue.count > value.count, "secure": secure,
      "settable": settable.boolValue && !secure,
      "actions": names as? [String] ?? [],
    ])
    elements[path] = element
    if !secure, let children = attribute(element, kAXChildrenAttribute) as? [AXUIElement] {
      for (index, child) in children.prefix(80).enumerated() {
        walk(child, "\(path).\(index)", depth + 1)
      }
    }
  }
  walk(root, "0", 0)
  return (nodes, elements)
}
// OCR supplements custom-drawn tables/charts without turning pixels into action
// targets. Capture stays in memory, bound to one visible window of the chosen pid.
func windowFrame(_ element: AXUIElement) -> CGRect? {
  guard let position = attribute(element, kAXPositionAttribute),
    let size = attribute(element, kAXSizeAttribute),
    CFGetTypeID(position) == AXValueGetTypeID(), CFGetTypeID(size) == AXValueGetTypeID()
  else { return nil }
  var point = CGPoint.zero
  var extent = CGSize.zero
  guard AXValueGetValue(unsafeBitCast(position, to: AXValue.self), .cgPoint, &point),
    AXValueGetValue(unsafeBitCast(size, to: AXValue.self), .cgSize, &extent)
  else { return nil }
  return CGRect(origin: point, size: extent)
}
func visualEvidence(_ pid: pid_t, _ expected: CGRect?, _ contextLabels: [String]) -> [String: Any] {
  _ = NSApplication.shared
  guard CGPreflightScreenCaptureAccess() else {
    return ["visual_status": "BLOCKED_EXTERNAL_SCREEN_RECORDING"]
  }
  var result: [String: Any] = ["visual_status": "UNAVAILABLE"]
  var finished = false
  var stage = "CONTENT"
  func complete(_ value: [String: Any]) {
    DispatchQueue.main.async {
      result = value
      finished = true
    }
  }
  SCShareableContent.getExcludingDesktopWindows(true, onScreenWindowsOnly: false) {
    content, error in
    let candidates =
      content?.windows.filter { window in
        guard
          window.owningApplication?.processID == pid && window.frame.width > 200
            && window.frame.height > 100
        else { return false }
        guard let expected = expected else { return true }
        return abs(window.frame.minX - expected.minX) < 6
          && abs(window.frame.minY - expected.minY) < 6
          && abs(window.frame.width - expected.width) < 6
          && abs(window.frame.height - expected.height) < 6
      } ?? []
    // Some custom windows omit AX geometry. Select the principal application
    // window only when its area is unambiguous; never cross the target pid.
    let ordered = candidates.sorted {
      $0.frame.width * $0.frame.height > $1.frame.width * $1.frame.height
    }
    let unique =
      ordered.count == 1
      || (ordered.count > 1
        && ordered[0].frame.width * ordered[0].frame.height > ordered[1].frame.width
          * ordered[1].frame.height * 1.05)
    guard error == nil, unique, let window = ordered.first else {
      complete([
        "visual_status": error != nil
          ? "CAPTURE_CONTENT_UNAVAILABLE"
          : (candidates.count > 1 ? "AMBIGUOUS_VISIBLE_WINDOW" : "NO_VISIBLE_WINDOW")
      ])
      return
    }
    DispatchQueue.main.async { stage = "IMAGE" }
    let configuration = SCStreamConfiguration()
    configuration.width = min(2880, Int(window.frame.width * 2))
    configuration.height = min(2160, Int(window.frame.height * 2))
    configuration.showsCursor = false
    let filter = SCContentFilter(desktopIndependentWindow: window)
    SCScreenshotManager.captureImage(contentFilter: filter, configuration: configuration) {
      image, error in
      guard error == nil, let image = image else {
        complete([
          "visual_status": "CAPTURE_IMAGE_UNAVAILABLE",
          "visual_error_code": (error as NSError?)?.code ?? 0,
        ])
        return
      }
      DispatchQueue.main.async { stage = "TEXT" }
      let request = VNRecognizeTextRequest()
      request.recognitionLevel = .accurate
      request.recognitionLanguages = ["zh-Hans", "en-US"]
      request.usesLanguageCorrection = false
      do {
        try VNImageRequestHandler(cgImage: image).perform([request])
        let observations = (request.results ?? []).sorted {
          if abs($0.boundingBox.midY - $1.boundingBox.midY) > 0.01 {
            return $0.boundingBox.midY > $1.boundingBox.midY
          }
          return $0.boundingBox.minX < $1.boundingBox.minX
        }
        let lines = observations.compactMap { $0.topCandidates(1).first?.string }
        let bitmap = NSBitmapImageRep(cgImage: image)
        let positioned: [[String: Any]] = observations.prefix(300).enumerated().compactMap {
          index, observation in
          guard let candidate = observation.topCandidates(1).first else { return nil }
          let box = observation.boundingBox
          func rounded(_ value: CGFloat) -> Double { (Double(value) * 1000).rounded() / 1000 }
          var highlighted = false
          if candidate.string.range(of: "^[0-9]+\\.[0-9]{2,}$", options: .regularExpression) != nil
          {
            let x0 = box.minX * CGFloat(image.width)
            let x1 = box.maxX * CGFloat(image.width)
            let y0 = (1 - box.maxY) * CGFloat(image.height)
            let y1 = (1 - box.minY) * CGFloat(image.height)
            let points = [
              CGPoint(x: x0 - 2, y: y0 - 2), CGPoint(x: x1 + 2, y: y0 - 2),
              CGPoint(x: x0 - 2, y: y1 + 2), CGPoint(x: x1 + 2, y: y1 + 2),
            ]
            let colors = points.compactMap { point in
              bitmap.colorAt(
                x: max(0, min(image.width - 1, Int(point.x))),
                y: max(0, min(image.height - 1, Int(point.y))))?.usingColorSpace(.deviceRGB)
            }
            if colors.count == 4 {
              let r = colors.map(\.redComponent).reduce(0, +) / 4
              let g = colors.map(\.greenComponent).reduce(0, +) / 4
              let b = colors.map(\.blueComponent).reduce(0, +) / 4
              highlighted = max(r, g, b) - min(r, g, b) > 0.07 && (r + g + b) / 3 > 0.5
            }
          }
          return [
            "highlighted": highlighted,
            "id": index, "text": String(candidate.string.prefix(500)),
            "box": [
              rounded(box.minX), rounded(1 - box.maxY), rounded(box.width), rounded(box.height),
            ],
          ]
        }
        let emphasized = positioned.filter { $0["highlighted"] as? Bool == true }
        let headings = positioned.filter { line in
          guard let text = line["text"] as? String, let box = line["box"] as? [Double] else {
            return false
          }
          return contextLabels.contains(text) && box[1] < 0.2
        }
        var readback: [String: Any] = [:]
        if let heading = headings.first, let headingBox = heading["box"] as? [Double] {
          let aligned = emphasized.filter { line in
            guard let box = line["box"] as? [Double] else { return false }
            return box[0] >= headingBox[0] - 0.06 && box[1] > headingBox[1] + 0.05
          }
          let values = Set(aligned.compactMap { $0["text"] as? String })
          if values.count == 1, let value = values.first {
            readback = [
              "context": heading["text"] ?? "", "value": value,
              "line_ids": aligned.compactMap { $0["id"] as? Int },
            ]
          }
        }
        complete([
          "primary_numeric_readback": readback,
          "visual_status": "OBSERVED",
          "visual_text": String(lines.joined(separator: "\n").prefix(16000)),
          "visual_lines": positioned,
          "highlighted_numeric_labels": positioned.filter { $0["highlighted"] as? Bool == true },
        ])
      } catch { complete(["visual_status": "OCR_FAILED"]) }
    }
  }
  let deadline = Date().addingTimeInterval(8)
  while !finished && Date() < deadline {
    RunLoop.current.run(until: Date().addingTimeInterval(0.05))
  }
  return finished ? result : ["visual_status": "OCR_TIMEOUT", "visual_stage": stage]
}

func execute(_ input: [String: Any]) -> [String: Any] {
  if input["command"] as? String == "status" {
    return [
      "accessibility": AXIsProcessTrusted(), "screen_recording": CGPreflightScreenCaptureAccess(),
      "platform": "macOS",
    ]
  }
  if input["command"] as? String == "resolve" {
    guard let name = input["bundle_id"] as? String else {
      return ["error": "COMPUTER_APP_NOT_INSTALLED"]
    }
    var resolved =
      NSWorkspace.shared.urlForApplication(withBundleIdentifier: name)
      ?? NSWorkspace.shared.fullPath(forApplication: name).map({ URL(fileURLWithPath: $0) })
    if resolved == nil {
      // Localized display names often differ from .app file names. Never choose
      // an arbitrary fuzzy match, particularly when multiple trading apps exist.
      func normalized(_ value: String) -> String {
        var result = value.lowercased().replacingOccurrences(of: " ", with: "")
        for suffix in [".app", "经典版"] {
          if result.hasSuffix(suffix) { result = String(result.dropLast(suffix.count)) }
        }
        return result
      }
      var matches = [URL]()
      for directory in [
        URL(fileURLWithPath: "/Applications"),
        FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Applications"),
      ] {
        for candidate
          in (try? FileManager.default.contentsOfDirectory(
            at: directory, includingPropertiesForKeys: nil)) ?? []
        {
          guard candidate.pathExtension == "app", let bundle = Bundle(url: candidate) else {
            continue
          }
          var names = [
            candidate.deletingPathExtension().lastPathComponent,
            bundle.object(forInfoDictionaryKey: "CFBundleDisplayName") as? String ?? "",
            bundle.object(forInfoDictionaryKey: "CFBundleName") as? String ?? "",
          ]
          // Read declared localizations, not just the server process locale.
          for language in bundle.localizations.prefix(30) {
            if let path = bundle.path(
              forResource: "InfoPlist", ofType: "strings", inDirectory: nil,
              forLocalization: language),
              let data = FileManager.default.contents(atPath: path),
              let info = (try? PropertyListSerialization.propertyList(from: data, format: nil))
                as? [String: Any]
            {
              names += [
                info["CFBundleDisplayName"] as? String ?? "", info["CFBundleName"] as? String ?? "",
              ]
            }
          }
          let requested = normalized(name)
          let minimumPrefix = requested.unicodeScalars.contains(where: { $0.value > 127 }) ? 2 : 4
          if names.contains(where: {
            let installed = normalized($0)
            return !installed.isEmpty
              && (installed == requested
                || (requested.count >= minimumPrefix && installed.hasPrefix(requested)))
          }) {
            matches.append(candidate)
          }
        }
      }
      if matches.count > 1 { return ["error": "COMPUTER_APP_NAME_AMBIGUOUS"] }
      resolved = matches.first
    }
    guard let url = resolved, url.pathExtension == "app",
      let bundle = Bundle(url: url)?.bundleIdentifier
    else { return ["error": "COMPUTER_APP_NOT_INSTALLED"] }
    return ["bundle_id": bundle]
  }
  guard AXIsProcessTrusted() else { return ["error": "COMPUTER_ACCESSIBILITY_PERMISSION_REQUIRED"] }
  if let session = CGSessionCopyCurrentDictionary() as? [String: Any],
    session["CGSSessionScreenIsLocked"] as? Bool == true
  {
    return ["error": "COMPUTER_SCREEN_LOCKED"]
  }
  guard let bundle = input["bundle_id"] as? String,
    let url = NSWorkspace.shared.urlForApplication(withBundleIdentifier: bundle)
  else {
    return ["error": "COMPUTER_APP_NOT_INSTALLED"]
  }
  var app = NSRunningApplication.runningApplications(withBundleIdentifier: bundle).first
  if input["action"] == nil {
    let configuration = NSWorkspace.OpenConfiguration()
    configuration.activates = true
    var finished = false
    NSWorkspace.shared.openApplication(at: url, configuration: configuration) { result, _ in
      app = result
      finished = true
    }
    let deadline = Date().addingTimeInterval(8)
    while !finished && Date() < deadline {
      RunLoop.current.run(until: Date().addingTimeInterval(0.05))
    }
  }
  guard let target = app else { return ["error": "COMPUTER_APP_UNAVAILABLE"] }
  let application = AXUIElementCreateApplication(target.processIdentifier)
  AXUIElementSetMessagingTimeout(application, 2)
  let navigation = input["navigate_url"] as? String
  if let navigation = navigation {
    guard bundle == "com.google.Chrome", input["action"] == nil,
      input["search_query"] == nil || input["search_query"] is NSNull,
      let address = URL(string: navigation), address.scheme == "https",
      address.user == nil, address.password == nil,
      let host = address.host, host.contains("."), host != "localhost",
      !host.hasSuffix(".local"), address.port == nil || address.port == 443
    else { return ["error": "COMPUTER_PUBLIC_HTTPS_REQUIRED"] }
    let configuration = NSWorkspace.OpenConfiguration()
    configuration.activates = true
    var finished = false
    var failed = false
    NSWorkspace.shared.open([address], withApplicationAt: url, configuration: configuration) {
      _, error in
      failed = error != nil
      finished = true
    }
    let deadline = Date().addingTimeInterval(4)
    while !finished && Date() < deadline {
      RunLoop.current.run(until: Date().addingTimeInterval(0.05))
    }
    guard finished && !failed else { return ["error": "COMPUTER_NAVIGATION_OPEN_FAILED"] }
  }
  let query = input["search_query"] as? String
  if let query = query, bundle == "com.google.Chrome" {
    guard !query.isEmpty, query.count <= 500,
      input["action"] == nil
    else { return ["error": "COMPUTER_SEARCH_REQUIRES_CHROME"] }
    var search = URLComponents(string: "https://www.google.com/search")!
    search.queryItems = [URLQueryItem(name: "q", value: query)]
    let configuration = NSWorkspace.OpenConfiguration()
    configuration.activates = true
    var finished = false
    var failed = false
    NSWorkspace.shared.open([search.url!], withApplicationAt: url, configuration: configuration) {
      _, error in
      failed = error != nil
      finished = true
    }
    let deadline = Date().addingTimeInterval(8)
    while !finished && Date() < deadline {
      RunLoop.current.run(until: Date().addingTimeInterval(0.05))
    }
    guard finished && !failed else { return ["error": "COMPUTER_SEARCH_OPEN_FAILED"] }
  }
  if bundle == "com.google.Chrome" {
    // Ask Chrome to expose rendered accessibility content; never execute page JS,
    // inspect profiles/cookies, or enable an unauthenticated debugging port.
    AXUIElementSetAttributeValue(application, "AXEnhancedUserInterface" as CFString, kCFBooleanTrue)
  }
  func currentRoot() -> AXUIElement {
    if let window = attribute(application, kAXFocusedWindowAttribute) {
      return unsafeBitCast(window, to: AXUIElement.self)
    }
    if let windows = attribute(application, kAXWindowsAttribute) as? [AXUIElement],
      let window = windows.first
    {
      return window
    }
    return application
  }
  var (nodes, elements) = tree(currentRoot())
  if nodes.count <= 1 && input["action"] == nil {
    // Launch completion precedes Qt/native accessibility tree initialization.
    let deadline = Date().addingTimeInterval(3)
    while nodes.count <= 1 && Date() < deadline {
      RunLoop.current.run(until: Date().addingTimeInterval(0.15))
      (nodes, elements) = tree(currentRoot())
    }
  }
  if let query = query, bundle != "com.google.Chrome" {
    guard !query.isEmpty, query.count <= 500, input["action"] == nil else {
      return ["error": "COMPUTER_NATIVE_SEARCH_UNAVAILABLE"]
    }
    let candidates = nodes.filter { node in
      guard node["secure"] as? Bool != true, node["settable"] as? Bool == true,
        ["AXTextField", "AXSearchField"].contains(node["role"] as? String ?? ""),
        (node["actions"] as? [String])?.contains("AXConfirm") == true,
        let id = node["id"] as? String
      else { return false }
      let placeholder = (node["placeholder"] as? String ?? "").lowercased()
      guard
        placeholder.contains("搜索") || placeholder.contains("search") || placeholder == "代码/拼音/名称"
      else { return false }
      return nodes.contains { parent in
        parent["role"] as? String == "AXToolbar"
          && id.hasPrefix((parent["id"] as? String ?? "") + ".")
      }
    }
    guard candidates.count == 1, let id = candidates.first?["id"] as? String,
      let field = elements[id]
    else {
      return ["error": "COMPUTER_NATIVE_SEARCH_UNAVAILABLE"]
    }
    // Only a verified toolbar search control can be submitted without write
    // approval. No arbitrary keys, trading tickets or arbitrary AX fields.
    target.activate(options: [.activateIgnoringOtherApps])
    RunLoop.current.run(until: Date().addingTimeInterval(0.1))
    _ = AXUIElementSetAttributeValue(field, kAXFocusedAttribute as CFString, kCFBooleanTrue)
    guard
      AXUIElementSetAttributeValue(field, kAXValueAttribute as CFString, query as CFString)
        == .success
    else {
      return ["error": "COMPUTER_NATIVE_SEARCH_UNVERIFIED"]
    }
    // Some native search fields expose AXConfirm but do not dispatch their
    // search delegate. A single fixed Return is allowed ONLY while this
    // verified toolbar search field still owns focus and the exact query value.
    if text(field, kAXValueAttribute) == query {
      _ = AXUIElementSetAttributeValue(field, kAXFocusedAttribute as CFString, kCFBooleanTrue)
      guard NSWorkspace.shared.frontmostApplication?.processIdentifier == target.processIdentifier,
        attribute(field, kAXFocusedAttribute) as? Bool == true,
        let down = CGEvent(keyboardEventSource: nil, virtualKey: 36, keyDown: true),
        let up = CGEvent(keyboardEventSource: nil, virtualKey: 36, keyDown: false)
      else { return ["error": "COMPUTER_NATIVE_SEARCH_FOCUS_CHANGED"] }
      down.post(tap: .cghidEventTap)
      up.post(tap: .cghidEventTap)
    }
    RunLoop.current.run(until: Date().addingTimeInterval(0.5))
    // Native search may first display candidates and clear the editor. Select
    // the current candidate only if focus remains in that same toolbar editor;
    // never send Return into a newly focused document or order form.
    if text(field, kAXValueAttribute).isEmpty,
      attribute(field, kAXFocusedAttribute) as? Bool == true,
      NSWorkspace.shared.frontmostApplication?.processIdentifier == target.processIdentifier,
      let down = CGEvent(keyboardEventSource: nil, virtualKey: 36, keyDown: true),
      let up = CGEvent(keyboardEventSource: nil, virtualKey: 36, keyDown: false)
    {
      down.post(tap: .cghidEventTap)
      up.post(tap: .cghidEventTap)
      RunLoop.current.run(until: Date().addingTimeInterval(0.4))
    }
    (nodes, elements) = tree(currentRoot())
  }
  if query != nil && bundle == "com.google.Chrome" {
    // Browser loads asynchronously after NSWorkspace acknowledges the URL. Bound
    // polling and read the visible document; opening a tab is not search success.
    let deadline = Date().addingTimeInterval(8)
    var loaded = false
    while Date() < deadline {
      let correctDocument = nodes.contains(where: { node in
        guard node["role"] as? String == "AXWebArea",
          let raw = node["url"] as? String, let address = URLComponents(string: raw)
        else { return false }
        return address.host == "www.google.com" && address.path == "/search"
          && address.queryItems?.first(where: { $0.name == "q" })?.value == query
      })
      let hasResult = nodes.contains(where: { node in
        guard node["role"] as? String == "AXLink",
          let raw = node["url"] as? String, let host = URL(string: raw)?.host
        else { return false }
        return host != "google.com" && !host.hasSuffix(".google.com")
          && host != "gstatic.com" && !host.hasSuffix(".gstatic.com")
          && !(node["title"] as? String ?? "").isEmpty
      })
      if correctDocument && hasResult {
        loaded = true
        break
      }
      RunLoop.current.run(until: Date().addingTimeInterval(0.2))
      (nodes, elements) = tree(currentRoot())
    }
    if !loaded { return ["error": "COMPUTER_SEARCH_PAGE_UNAVAILABLE"] }
  }
  if let navigation = navigation, let expected = URL(string: navigation) {
    let deadline = Date().addingTimeInterval(8)
    var loaded = false
    while Date() < deadline {
      let correctPage = nodes.contains { node in
        guard node["role"] as? String == "AXWebArea", let raw = node["url"] as? String,
          let actual = URL(string: raw)
        else { return false }
        return actual.host == expected.host && actual.path == expected.path
      }
      let hasContent = nodes.contains {
        $0["role"] as? String == "AXLink" && !($0["url"] as? String ?? "").isEmpty
      }
      if correctPage && hasContent {
        loaded = true
        break
      }
      RunLoop.current.run(until: Date().addingTimeInterval(0.2))
      (nodes, elements) = tree(currentRoot())
    }
    if !loaded {
      // A browser acknowledgement is not page readiness. Keep the existing Run
      // alive for a subsequent observation rather than claiming a permission fault.
      return ["status": "loading", "target_url": navigation, "nodes": []]
    }
  }
  guard nodes.count > 1 else { return ["error": "COMPUTER_APP_CONTROLS_UNAVAILABLE"] }
  let serialized = try! JSONSerialization.data(withJSONObject: nodes, options: [.sortedKeys])
  let hash = SHA256.hash(data: serialized).map { String(format: "%02x", $0) }.joined()
  if let action = input["action"] as? String {
    guard input["tree_hash"] as? String == hash,
      input["pid"] as? Int == Int(target.processIdentifier),
      let id = input["element_id"] as? String, let element = elements[id],
      let node = nodes.first(where: { $0["id"] as? String == id }), node["secure"] as? Bool != true
    else {
      return ["error": "COMPUTER_STALE_OBSERVATION"]
    }
    var error: AXError = .actionUnsupported
    if action == "press", (node["actions"] as? [String])?.contains(kAXPressAction) == true {
      error = AXUIElementPerformAction(element, kAXPressAction as CFString)
    } else if action == "confirm", (node["actions"] as? [String])?.contains("AXConfirm") == true {
      error = AXUIElementPerformAction(element, "AXConfirm" as CFString)
    } else if action == "set_value", node["settable"] as? Bool == true,
      let value = input["text"] as? String
    {
      error = AXUIElementSetAttributeValue(
        element, kAXValueAttribute as CFString, value as CFString)
    }
    guard error == .success else { return ["error": "COMPUTER_ACTION_RESULT_UNVERIFIED"] }
    return [
      "receipt": "AX_COMMAND_APPLIED", "bundle_id": bundle, "pid": Int(target.processIdentifier),
    ]
  }
  var snapshot: [String: Any] = [
    "bundle_id": bundle, "pid": Int(target.processIdentifier), "nodes": nodes, "tree_hash": hash,
    "receipt": "OBSERVED",
  ]
  if bundle != "com.google.Chrome" {
    snapshot.merge(
      visualEvidence(
        target.processIdentifier, windowFrame(currentRoot()),
        nodes.compactMap { node in
          guard node["role"] as? String == "AXStaticText", let value = node["value"] as? String,
            value.range(of: "^[A-Z0-9]{3,12}(:[A-Za-z]+)?$", options: .regularExpression) != nil
          else { return nil }
          return value
        })
    ) { _, new in
      new
    }
  }
  return snapshot
}
do {
  let data = FileHandle.standardInput.readDataToEndOfFile()
  let body = try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
  respond(execute(body))
} catch { respond(["error": "COMPUTER_INVALID_REQUEST"]) }
