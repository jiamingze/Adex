import Foundation

/// Native audio transport: serial PCM/finish ordering, independent of WebView touch tracking.
final class SpeechStream: @unchecked Sendable {
    private let queue = DispatchQueue(label: "io.adex.speech.stream")
    private var socket: URLSessionWebSocketTask?
    private var frames = [Data]()
    private var bytes = 0
    private var ready = false
    private var ended = false
    private var sending = false
    private var finishSent = false
    private var closed = false
    var partial: ((String) -> Void)?
    var result: ((String?, String?) -> Void)?

    func append(_ pcm: Data) {
        queue.async {
            guard !self.closed, !self.ended else { return }
            self.bytes += pcm.count
            guard self.bytes <= 1_440_000 else { self.complete(nil, "SPEECH_AUDIO_LIMIT"); return }
            self.frames.append(pcm)
            self.pump()
        }
    }
    func connect(url: URL, token: String) {
        queue.async {
            guard !self.closed, self.socket == nil, url.scheme == "wss", token.count < 2048 else {
                self.complete(nil, "SPEECH_CONNECTION_FAILED"); return
            }
            let socket = URLSession.shared.webSocketTask(with: url)
            self.socket = socket
            socket.resume()
            let auth = try! JSONSerialization.data(withJSONObject: ["token": token])
            self.sending = true
            Task {
                do {
                    try await socket.send(.string(String(data: auth, encoding: .utf8)!))
                    self.queue.async { self.sending = false; self.pump() }
                } catch { self.queue.async { self.complete(nil, "SPEECH_CONNECTION_FAILED") } }
            }
            self.receive(socket)
            self.queue.asyncAfter(deadline: .now()+60) {
                if !self.closed { self.complete(nil, "SPEECH_TIMEOUT") }
            }
        }
    }
    func finish() {
        queue.async { self.ended = true; self.pump() }
    }
    func cancel() {
        queue.async { self.complete(nil, "SPEECH_CANCELLED") }
    }
    private func pump() {
        guard !closed, ready, !sending, let socket = socket else { return }
        let message: URLSessionWebSocketTask.Message
        if !frames.isEmpty { message = .data(frames.removeFirst()) }
        else if ended && !finishSent { finishSent = true; message = .string("{\"type\":\"finish\"}") }
        else { return }
        sending = true
        Task {
            do {
                try await socket.send(message)
                self.queue.async { self.sending = false; self.pump() }
            } catch { self.queue.async { self.complete(nil, "SPEECH_CONNECTION_FAILED") } }
        }
    }
    private func receive(_ socket: URLSessionWebSocketTask) {
        Task {
            do {
                let message = try await socket.receive()
                self.queue.async {
                    guard !self.closed else { return }
                    let bytes: Data
                    switch message {
                    case .data(let data): bytes = data
                    case .string(let text): bytes = Data(text.utf8)
                    @unknown default: self.complete(nil, "SPEECH_INVALID_EVENT"); return
                    }
                    guard let event = (try? JSONSerialization.jsonObject(with: bytes)) as? [String: Any] else {
                        self.complete(nil, "SPEECH_INVALID_EVENT"); return
                    }
                    switch event["type"] as? String {
                    case "ready": self.ready = true; self.pump()
                    case "partial": self.partial?(event["text"] as? String ?? "")
                    case "final":
                        guard self.finishSent else { self.complete(nil, "SPEECH_INCOMPLETE"); return }
                        self.complete(event["text"] as? String ?? "", nil); return
                    case "error": self.complete(nil, "SPEECH_UNAVAILABLE"); return
                    default: break
                    }
                    self.receive(socket)
                }
            } catch { self.queue.async { self.complete(nil, "SPEECH_INCOMPLETE") } }
        }
    }
    private func complete(_ text: String?, _ error: String?) {
        guard !closed else { return }
        closed = true; frames.removeAll()
        socket?.cancel(with: .normalClosure, reason: nil); socket = nil
        let callback = result; result = nil; partial = nil
        callback?(text, error)
    }
}
