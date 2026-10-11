import Capacitor
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
    @objc public func start(_ call: CAPPluginCall) {
        guard pending == nil else { call.reject("SPEECH_BUSY"); return }
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
                        try session.setActive(true, options: .notifyOthersOnDeactivation)
                        let request = SFSpeechAudioBufferRecognitionRequest(); request.requiresOnDeviceRecognition = recognizer.supportsOnDeviceRecognition; request.shouldReportPartialResults = true
                        self.pending = call; self.request = request; self.text = ""
                        let node = self.engine.inputNode
                        node.installTap(onBus: 0, bufferSize: 1024, format: node.outputFormat(forBus: 0)) { buffer, _ in request.append(buffer) }
                        self.tapInstalled = true
                        self.engine.prepare(); try self.engine.start()
                        self.task = recognizer.recognitionTask(with: request) { result, error in
                            if let result = result { self.text = result.bestTranscription.formattedString }
                            DispatchQueue.main.async {
                                guard self.pending === call else { return }
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
        guard let call = pending else { return }; pending = nil
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
        guard let call = pending else { return }; pending = nil
        cleanup(); call.reject(reason)
    }
    @objc public func stop(_ call: CAPPluginCall) {
        guard let original = pending else { call.resolve(); return }
        if !engine.isRunning { finish(); call.resolve(); return }
        engine.stop()
        if tapInstalled { engine.inputNode.removeTap(onBus: 0); tapInstalled = false }
        request?.endAudio()
        // Give the recognizer time to return the last spoken words after release.
        DispatchQueue.main.asyncAfter(deadline: .now()+1.5) { if self.pending === original { self.finish() } }
        call.resolve()
    }
}
