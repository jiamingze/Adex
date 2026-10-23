import Foundation

if CommandLine.arguments.count == 1 {
    let stream = SpeechStream()
    let done = DispatchSemaphore(value: 0)
    var callbacks = 0
    stream.result = { text, error in
        callbacks += 1
        precondition(text == nil && error == "SPEECH_CANCELLED")
        done.signal()
    }
    stream.append(Data([0, 0])); stream.finish(); stream.cancel(); stream.cancel()
    precondition(done.wait(timeout: .now()+2) == .success)
    Thread.sleep(forTimeInterval: 0.05)
    precondition(callbacks == 1)
    print("PASS: native speech cancellation settles once and never needs a provider")
} else {
    // Explicit synthetic live acceptance, private input file contains only a short-lived ticket.
    let config = try! JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))) as! [String: String]
    let pcm = try! Data(contentsOf: URL(fileURLWithPath: config["pcm_path"]!))
    let stream = SpeechStream(), done = DispatchSemaphore(value: 0), lock = NSLock()
    var finishedSending = false, earlyPartial = false, finalCount = 0, failure: String?
    stream.partial = { text in
        lock.lock(); defer { lock.unlock() }
        if !text.isEmpty && !finishedSending { earlyPartial = true }
    }
    stream.result = { text, error in
        lock.lock(); finalCount = text?.count ?? 0; failure = error; lock.unlock()
        done.signal()
    }
    stream.connect(url: URL(string: config["url"]!)!, token: config["token"]!)
    // Real-time paced audio, not a file upload masquerading as streaming.
    for _ in 0..<3 {
        for offset in stride(from: 0, to: pcm.count, by: 3200) {
            stream.append(pcm.subdata(in: offset..<min(pcm.count, offset+3200)))
            Thread.sleep(forTimeInterval: 0.1)
        }
    }
    lock.lock(); finishedSending = true; lock.unlock()
    stream.finish()
    precondition(done.wait(timeout: .now()+20) == .success)
    precondition(failure == nil && earlyPartial && finalCount > 0)
    print("PASS: native URLSession received nonempty transcription BEFORE release and a final result")
}
