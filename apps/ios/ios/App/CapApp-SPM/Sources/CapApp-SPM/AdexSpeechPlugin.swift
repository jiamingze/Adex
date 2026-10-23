import Capacitor
import AVFoundation
import UIKit

/// Capture only. Alibaba recognition and credentials belong to the server.
@objc(AdexSpeechPlugin)
public class AdexSpeechPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "AdexSpeechPlugin"
    public let jsName = "AdexSpeech"
    public let pluginMethods: [CAPPluginMethod] = [CAPPluginMethod(name: "start", returnType: CAPPluginReturnPromise), CAPPluginMethod(name: "stop", returnType: CAPPluginReturnPromise)]
    private let engine = AVAudioEngine()
    private let gate = SpeechGestureGate()
    private var activeID: String?
    private var tapInstalled = false
    private var pending: CAPPluginCall?

    @objc public func start(_ call: CAPPluginCall) {
        guard let id = call.getString("session_id"), gate.begin(id) else { call.reject("SPEECH_CANCELLED"); return }
        activeID = id; pending = call
        AVAudioSession.sharedInstance().requestRecordPermission { granted in
            DispatchQueue.main.async {
                guard self.activeID == id else { return }
                guard granted else { self.cleanup("MICROPHONE_PERMISSION_DENIED"); return }
                do {
                    let session = AVAudioSession.sharedInstance()
                    try session.setCategory(.record, mode: .measurement, options: .duckOthers)
                    try? session.setAllowHapticsAndSystemSoundsDuringRecording(true)
                    try session.setActive(true)
                    let node = self.engine.inputNode
                    let inputFormat = node.outputFormat(forBus: 0)
                    guard let target = AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: 16000, channels: 1, interleaved: true),
                          let converter = AVAudioConverter(from: inputFormat, to: target) else { throw NSError(domain: "SPEECH_FORMAT", code: 1) }
                    node.installTap(onBus: 0, bufferSize: 2048, format: inputFormat) { buffer, _ in
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
                        DispatchQueue.main.async {
                            guard self.activeID == id else { return }
                            self.notifyListeners("audio", data: ["session_id": id, "pcm": data.base64EncodedString()])
                        }
                    }
                    self.tapInstalled = true
                    self.engine.prepare(); try self.engine.start()
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                    self.pending = nil; call.resolve()
                    DispatchQueue.main.asyncAfter(deadline: .now()+45) { if self.activeID == id { self.cleanup() } }
                } catch { self.cleanup("SPEECH_CAPTURE_FAILED") }
            }
        }
    }
    private func cleanup(_ reason: String = "SPEECH_CANCELLED") {
        activeID = nil; gate.finish()
        engine.stop()
        if tapInstalled { engine.inputNode.removeTap(onBus: 0); tapInstalled = false }
        pending?.reject(reason); pending = nil
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }
    @objc public func stop(_ call: CAPPluginCall) {
        if let id = call.getString("session_id"), gate.stop(id) { cleanup() }
        call.resolve()
    }
}
