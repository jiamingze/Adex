import Capacitor
import AVFoundation
import Speech
import UIKit

/// Native local recognition preserves the displayed utterance; Alibaba is the cloud fallback.
@objc(AdexSpeechPlugin)
public class AdexSpeechPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "AdexSpeechPlugin"
    public let jsName = "AdexSpeech"
    public let pluginMethods: [CAPPluginMethod] = [CAPPluginMethod(name: "start", returnType: CAPPluginReturnPromise), CAPPluginMethod(name: "stop", returnType: CAPPluginReturnPromise), CAPPluginMethod(name: "connect", returnType: CAPPluginReturnPromise), CAPPluginMethod(name: "cancel", returnType: CAPPluginReturnPromise)]
    private let engine = AVAudioEngine()
    private let gate = SpeechGestureGate()
    private var activeID: String?
    private var tapInstalled = false
    private var pending: CAPPluginCall?
    private var connectionCall: CAPPluginCall?
    private var stream: SpeechStream?
    private var previewRequest: SFSpeechAudioBufferRecognitionRequest?
    private var previewTask: SFSpeechRecognitionTask?
    private var localDraftActive = false
    private var choice = SpeechTranscriptChoice()
    private var settleTimer: DispatchWorkItem?

    @objc public func start(_ call: CAPPluginCall) {
        guard let id = call.getString("session_id"), gate.begin(id) else { call.reject("SPEECH_CANCELLED"); return }
        activeID = id; pending = call; choice = SpeechTranscriptChoice()
        let stream = SpeechStream(); self.stream = stream
        stream.partial = { [weak self] text in
            DispatchQueue.main.async {
                guard self?.activeID == id, self?.choice.draft.isEmpty == true else { return }
                self?.notifyListeners("partial", data: ["session_id": id, "text": text])
            }
        }
        stream.result = { [weak self] text, error in
            DispatchQueue.main.async {
                guard let self = self, self.activeID == id else { return }
                self.choice.cloud = text; self.choice.cloudError = error
                self.settleIfReady()
            }
        }
        AVAudioSession.sharedInstance().requestRecordPermission { granted in
            DispatchQueue.main.async {
                guard self.activeID == id else { return }
                guard granted else { self.cleanup("MICROPHONE_PERMISSION_DENIED"); return }
                do {
                    let session = AVAudioSession.sharedInstance()
                    try session.setCategory(.record, mode: .measurement, options: .duckOthers)
                    try? session.setAllowHapticsAndSystemSoundsDuringRecording(true)
                    try session.setActive(true)
                    // Preserve the accurate on-device utterance; the cloud must not
                    // overwrite what the user just saw. Cloud covers unavailable local ASR.
                    self.startLocalDraft(id)
                    let localRequest = self.previewRequest
                    let node = self.engine.inputNode
                    let inputFormat = node.outputFormat(forBus: 0)
                    guard let target = AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: 16000, channels: 1, interleaved: true),
                          let converter = AVAudioConverter(from: inputFormat, to: target) else { throw NSError(domain: "SPEECH_FORMAT", code: 1) }
                    node.installTap(onBus: 0, bufferSize: 2048, format: inputFormat) { buffer, _ in
                        localRequest?.append(buffer)
                        let capacity = AVAudioFrameCount(Double(buffer.frameLength) * 16000 / inputFormat.sampleRate) + 32
                        guard let output = AVAudioPCMBuffer(pcmFormat: target, frameCapacity: capacity) else { return }
                        var supplied = false
                        var conversionError: NSError?
                        converter.convert(to: output, error: &conversionError) { _, status in
                            if supplied { status.pointee = .noDataNow; return nil }
                            supplied = true; status.pointee = .haveData; return buffer
                        }
                        guard conversionError == nil, output.frameLength > 0, let samples = output.int16ChannelData else { return }
                        let data = Data(bytes: samples[0], count: Int(output.frameLength) * 2)
                        stream.append(data)
                    }
                    self.tapInstalled = true
                    self.engine.prepare(); try self.engine.start()
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                    self.pending = nil; call.resolve()
                    DispatchQueue.main.asyncAfter(deadline: .now()+45) { if self.activeID == id { self.releaseCapture() } }
                } catch { self.cleanup("SPEECH_CAPTURE_FAILED") }
            }
        }
    }
    private func cleanup(_ reason: String = "SPEECH_CANCELLED") {
        activeID = nil; gate.finish()
        stopCapture()
        settleTimer?.cancel(); settleTimer = nil
        localDraftActive = false
        previewTask?.cancel(); previewTask = nil; previewRequest = nil
        stream?.cancel(); stream = nil
        connectionCall?.reject(reason); connectionCall = nil
        pending?.reject(reason); pending = nil
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }
    private func startLocalDraft(_ id: String) {
        // No permission prompt or remote Apple recognition as a hidden fallback.
        // Existing device authorization and an on-device language pack are required.
        guard SFSpeechRecognizer.authorizationStatus() == .authorized,
            let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "zh-CN")),
            recognizer.isAvailable, recognizer.supportsOnDeviceRecognition else { return }
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.requiresOnDeviceRecognition = true; request.shouldReportPartialResults = true
        previewRequest = request; localDraftActive = true; choice.localAvailable = true
        previewTask = recognizer.recognitionTask(with: request) { [weak self] result, error in
            DispatchQueue.main.async {
                guard let self = self, self.activeID == id, self.localDraftActive else { return }
                if let result = result {
                    self.choice.preview(result.bestTranscription.formattedString)
                    if result.isFinal { self.choice.localFinal(result.bestTranscription.formattedString) }
                    self.notifyListeners("partial", data: ["session_id": id, "text": result.bestTranscription.formattedString, "draft": true])
                }
                if error != nil || result?.isFinal == true { self.localDraftActive = false }
                self.settleIfReady()
            }
        }
    }
    private func stopCapture() {
        engine.stop()
        if tapInstalled { engine.inputNode.removeTap(onBus: 0); tapInstalled = false }
        previewRequest?.endAudio()
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }
    private func releaseCapture() {
        guard !choice.released else { return }
        choice.released = true
        stopCapture(); stream?.finish()
        let id = activeID
        let timer = DispatchWorkItem { [weak self] in
            guard let self = self, self.activeID == id else { return }
            self.choice.graceEnded = true; self.settleIfReady()
        }
        settleTimer = timer
        DispatchQueue.main.asyncAfter(deadline: .now()+0.8, execute: timer)
        settleIfReady()
    }
    private func settleIfReady() {
        guard let call = connectionCall else { return }
        if let text = choice.selection() {
            connectionCall = nil; cleanup(); call.resolve(["text": text])
        } else if choice.failed {
            let error = choice.cloudError ?? "SPEECH_UNAVAILABLE"
            connectionCall = nil; cleanup(); call.reject(error)
        }
    }
    @objc public func connect(_ call: CAPPluginCall) {
        guard let id = call.getString("session_id"), activeID == id, connectionCall == nil,
            let address = call.getString("url"), let url = URL(string: address), url.scheme == "wss",
            let token = call.getString("token"), let stream = stream else { call.reject("SPEECH_SESSION_REQUIRED"); return }
        connectionCall = call; settleIfReady()
        if activeID == id { stream.connect(url: url, token: token) }
    }
    @objc public func cancel(_ call: CAPPluginCall) {
        if let id = call.getString("session_id") { _ = gate.stop(id); if activeID == id { cleanup() } }
        call.resolve()
    }
    @objc public func stop(_ call: CAPPluginCall) {
        if let id = call.getString("session_id"), gate.stop(id) {
            if pending != nil { cleanup() }
            else { releaseCapture() }
        }
        call.resolve()
    }
}
