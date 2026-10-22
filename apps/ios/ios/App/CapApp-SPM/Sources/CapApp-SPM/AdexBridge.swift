import Capacitor
import UIKit
import Security
import Speech
import AVFoundation

public class AdexBridge: CAPBridgeViewController {
    public override func capacitorDidLoad() {
        webView?.scrollView.bounces = false
        webView?.scrollView.alwaysBounceHorizontal = false
        webView?.scrollView.alwaysBounceVertical = false
        webView?.scrollView.isScrollEnabled = false
        webView?.allowsBackForwardNavigationGestures = false
        bridge?.registerPluginInstance(SecureSessionPlugin())
        bridge?.registerPluginInstance(AdexSpeechPlugin())
        bridge?.registerPluginInstance(AdexLocationPlugin())
        bridge?.registerPluginInstance(AdexPushPlugin())
        bridge?.registerPluginInstance(AdexCalendarPlugin())
    }
}

@objc(SecureSessionPlugin)
public class SecureSessionPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "SecureSessionPlugin"
    public let jsName = "SecureSession"
    public let pluginMethods: [CAPPluginMethod] = [CAPPluginMethod(name: "get", returnType: CAPPluginReturnPromise), CAPPluginMethod(name: "set", returnType: CAPPluginReturnPromise), CAPPluginMethod(name: "clear", returnType: CAPPluginReturnPromise)]
    private var query: [String: Any] { [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: "io.adex.personal", kSecAttrAccount as String: "session"] }
    @objc public func get(_ call: CAPPluginCall) {
        var q = query; q[kSecReturnData as String] = true; q[kSecMatchLimit as String] = kSecMatchLimitOne
        var data: CFTypeRef?
        let result = SecItemCopyMatching(q as CFDictionary, &data)
        if result == errSecItemNotFound { call.resolve(["token": ""]); return }
        guard result == errSecSuccess, let bytes = data as? Data else { call.reject("KEYCHAIN_UNAVAILABLE"); return }
        call.resolve(["token": String(data: bytes, encoding: .utf8) ?? ""])
    }
    @objc public func set(_ call: CAPPluginCall) {
        guard let token = call.getString("token"), token.count < 512 else { call.reject("INVALID_TOKEN"); return }
        let attributes: [String: Any] = [kSecValueData as String: token.data(using: .utf8)!, kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly]
        var result = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
        if result == errSecItemNotFound {
            var q = query; attributes.forEach { q[$0.key] = $0.value }
            result = SecItemAdd(q as CFDictionary, nil)
        }
        guard result == errSecSuccess else { call.reject("KEYCHAIN_UNAVAILABLE"); return }
        call.resolve()
    }
    @objc public func clear(_ call: CAPPluginCall) { SecItemDelete(query as CFDictionary); call.resolve() }
}

@objc(AdexSpeechPlugin)
public class AdexSpeechPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "AdexSpeechPlugin"
    public let jsName = "AdexSpeech"
    public let pluginMethods: [CAPPluginMethod] = [CAPPluginMethod(name: "start", returnType: CAPPluginReturnPromise), CAPPluginMethod(name: "stop", returnType: CAPPluginReturnPromise)]
    private let engine = AVAudioEngine()
    private var task: SFSpeechRecognitionTask?
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var pending: CAPPluginCall?
    private var text = ""
    private var tapInstalled = false
    private let gestureGate = SpeechGestureGate()
    @objc public func start(_ call: CAPPluginCall) {
        guard let id = call.getString("session_id"), !id.isEmpty else { call.reject("SPEECH_SESSION_REQUIRED"); return }
        // stop can reach the bridge before start while permissions initialize.
        // A stopped gesture must never activate the microphone afterwards.
        guard pending == nil else { call.reject("SPEECH_BUSY"); return }
        guard gestureGate.begin(id) else { call.reject("SPEECH_CANCELLED"); return }
        pending = call
        SFSpeechRecognizer.requestAuthorization { status in
            guard status == .authorized else { DispatchQueue.main.async { if self.pending === call { self.fail("SPEECH_PERMISSION_DENIED") } }; return }
            AVAudioSession.sharedInstance().requestRecordPermission { granted in
                DispatchQueue.main.async {
                    guard self.pending === call else { return }
                    guard granted else { self.fail("MICROPHONE_PERMISSION_DENIED"); return }
                    guard let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "zh-CN")), recognizer.isAvailable else { self.fail("ON_DEVICE_SPEECH_UNAVAILABLE"); return }
                    do {
                        let session = AVAudioSession.sharedInstance()
                        try session.setCategory(.record, mode: .measurement, options: .duckOthers)
                        // Recording suppresses haptics by default. This is optional:
                        // lack of tactile feedback must never block microphone use.
                        try? session.setAllowHapticsAndSystemSoundsDuringRecording(true)
                        try session.setActive(true, options: .notifyOthersOnDeactivation)
                        let request = SFSpeechAudioBufferRecognitionRequest(); request.requiresOnDeviceRecognition = recognizer.supportsOnDeviceRecognition; request.shouldReportPartialResults = true
                        self.pending = call; self.request = request; self.text = ""
                        let node = self.engine.inputNode
                        node.installTap(onBus: 0, bufferSize: 1024, format: node.outputFormat(forBus: 0)) { buffer, _ in request.append(buffer) }
                        self.tapInstalled = true
                        let feedback = UIImpactFeedbackGenerator(style: .light)
                        feedback.prepare()
                        self.engine.prepare(); try self.engine.start()
                        // Confirm actual capture, not pointer-down or permission prompts.
                        // This path runs once on main, after the gesture identity guard.
                        feedback.impactOccurred()
                        self.task = recognizer.recognitionTask(with: request) { result, error in
                            DispatchQueue.main.async {
                                guard self.pending === call else { return }
                                if let result = result {
                                    self.text = result.bestTranscription.formattedString
                                    self.notifyListeners("partial", data: ["session_id": id, "text": self.text])
                                }
                                if error != nil { self.fail("SPEECH_RECOGNITION_FAILED") }
                                else if result?.isFinal == true { self.finish() }
                            }
                        }
                        DispatchQueue.main.asyncAfter(deadline: .now()+45) { if self.pending === call { self.finish() } }
                    } catch { self.fail("SPEECH_START_FAILED") }
                }
            }
        }
    }
    private func finish() {
        guard let call = pending else { return }; pending = nil; gestureGate.finish()
        cleanup()
        try? AVAudioSession.sharedInstance().setActive(false)
        call.resolve(["text": text, "provider": "ios-speech"])
    }
    private func cleanup() {
        engine.stop()
        if tapInstalled { engine.inputNode.removeTap(onBus: 0); tapInstalled = false }
        request?.endAudio(); task?.cancel(); task = nil; request = nil
        try? AVAudioSession.sharedInstance().setActive(false)
    }
    private func fail(_ reason: String) {
        guard let call = pending else { return }; pending = nil; gestureGate.finish()
        cleanup(); call.reject(reason)
    }
    @objc public func stop(_ call: CAPPluginCall) {
        guard let id = call.getString("session_id"), !id.isEmpty else { call.resolve(); return }
        guard gestureGate.stop(id), let original = pending else { call.resolve(); return }
        if !engine.isRunning { finish(); call.resolve(); return }
        engine.stop()
        if tapInstalled { engine.inputNode.removeTap(onBus: 0); tapInstalled = false }
        request?.endAudio()
        // Give the recognizer time to return the last spoken words after release.
        DispatchQueue.main.asyncAfter(deadline: .now()+1.5) { if self.pending === original { self.finish() } }
        call.resolve()
    }
}

// Push navigation carries only a notification identifier. The authenticated server
// resolves its owner-scoped conversation/run/action; payload URLs are never opened.
import UserNotifications

public class AdexNotificationCoordinator: NSObject, UNUserNotificationCenterDelegate {
    public static let shared = AdexNotificationCoordinator()
    public var onToken: ((String) -> Void)?
    public var onError: (() -> Void)?
    public var onTap: ((String) -> Void)?
    public func configure() { UNUserNotificationCenter.current().delegate = self }
    public func registered(_ data: Data) { onToken?(data.map { String(format: "%02x", $0) }.joined()) }
    public func failed() { onError?() }
    public func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse, withCompletionHandler completionHandler: @escaping () -> Void) {
        if let id = response.notification.request.content.userInfo["notification_id"] as? String, UUID(uuidString: id) != nil {
            UserDefaults.standard.set(id, forKey: "adex.pendingNotification")
            DispatchQueue.main.async { self.onTap?(id) }
        }
        completionHandler()
    }
    public func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification, withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) { completionHandler([.banner, .sound]) }
}

@objc(AdexPushPlugin)
public class AdexPushPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "AdexPushPlugin"
    public let jsName = "AdexPush"
    public let pluginMethods: [CAPPluginMethod] = [CAPPluginMethod(name: "request", returnType: CAPPluginReturnPromise), CAPPluginMethod(name: "pending", returnType: CAPPluginReturnPromise), CAPPluginMethod(name: "acknowledge", returnType: CAPPluginReturnPromise)]
    private var registration: CAPPluginCall?
    public override func load() {
        let coordinator = AdexNotificationCoordinator.shared
        coordinator.configure()
        coordinator.onToken = { [weak self] token in
            let mode = Bundle.main.object(forInfoDictionaryKey: "AdexAPNSEnvironment") as? String
            guard mode == "development" || mode == "production" else { self?.registration?.reject("APNS_SIGNING_NOT_CONFIGURED"); self?.registration = nil; return }
            self?.registration?.resolve(["token": token, "environment": mode == "development" ? "sandbox" : "production"])
            self?.registration = nil
        }
        coordinator.onError = { [weak self] in self?.registration?.reject("APNS_REGISTRATION_UNAVAILABLE"); self?.registration = nil }
        coordinator.onTap = { [weak self] id in self?.notifyListeners("tap", data: ["notification_id": id]) }
    }
    @objc func request(_ call: CAPPluginCall) {
        if registration != nil { call.reject("PUSH_REGISTRATION_BUSY"); return }
        if call.getBool("prompt") == false {
            // Session restoration must never open a permission prompt or depend on a
            // local web-storage hint that logout/reinstallation deliberately removes.
            UNUserNotificationCenter.current().getNotificationSettings { [weak self] settings in
                DispatchQueue.main.async {
                    guard settings.authorizationStatus == .authorized || settings.authorizationStatus == .provisional else {
                        call.reject("PUSH_PERMISSION_DENIED"); return
                    }
                    self?.register(call)
                }
            }
            return
        }
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { [weak self] granted, error in
            DispatchQueue.main.async {
                guard granted, error == nil else { call.reject("PUSH_PERMISSION_DENIED"); return }
                self?.register(call)
            }
        }
    }
    private func register(_ call: CAPPluginCall) {
        guard registration == nil else { call.reject("PUSH_REGISTRATION_BUSY"); return }
        registration = call
        UIApplication.shared.registerForRemoteNotifications()
        DispatchQueue.main.asyncAfter(deadline: .now() + 15) { [weak self] in
            if self?.registration === call { call.reject("APNS_REGISTRATION_UNAVAILABLE"); self?.registration = nil }
        }
    }
    @objc func pending(_ call: CAPPluginCall) { call.resolve(["notification_id": UserDefaults.standard.string(forKey: "adex.pendingNotification") ?? ""]) }
    @objc func acknowledge(_ call: CAPPluginCall) { UserDefaults.standard.removeObject(forKey: "adex.pendingNotification"); call.resolve() }
}
