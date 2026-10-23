import AppKit
import ApplicationServices
import CryptoKit

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
func execute(_ input: [String: Any]) -> [String: Any] {
  if input["command"] as? String == "status" {
    return ["accessibility": AXIsProcessTrusted(), "platform": "macOS"]
  }
  if input["command"] as? String == "resolve" {
    guard let name = input["bundle_id"] as? String,
      let url = NSWorkspace.shared.urlForApplication(withBundleIdentifier: name)
        ?? NSWorkspace.shared.fullPath(forApplication: name).map({ URL(fileURLWithPath: $0) }),
      url.pathExtension == "app", let bundle = Bundle(url: url)?.bundleIdentifier
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
  if app == nil && input["action"] == nil {
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
  let query = input["search_query"] as? String
  if let query = query {
    guard bundle == "com.google.Chrome", !query.isEmpty, query.count <= 500,
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
    if bundle == "com.google.Chrome", let window = attribute(application, kAXFocusedWindowAttribute)
    {
      return unsafeBitCast(window, to: AXUIElement.self)
    }
    return application
  }
  var (nodes, elements) = tree(currentRoot())
  if query != nil {
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
  return [
    "bundle_id": bundle, "pid": Int(target.processIdentifier), "nodes": nodes, "tree_hash": hash,
    "receipt": "OBSERVED",
  ]
}
do {
  let data = FileHandle.standardInput.readDataToEndOfFile()
  let body = try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
  respond(execute(body))
} catch { respond(["error": "COMPUTER_INVALID_REQUEST"]) }
