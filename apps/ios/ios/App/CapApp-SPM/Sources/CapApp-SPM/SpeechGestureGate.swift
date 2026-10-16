import Foundation

/// Serial bridge state: a released gesture cannot start later, and a stale stop
/// cannot terminate a newer gesture. This is independent of permission timing.
final class SpeechGestureGate {
    private var activeID: String?
    private var stopped: [String] = []

    func begin(_ id: String) -> Bool {
        guard activeID == nil, !stopped.contains(id) else { return false }
        activeID = id
        return true
    }

    func stop(_ id: String) -> Bool {
        if !stopped.contains(id) { stopped.append(id) }
        if stopped.count > 32 { stopped.removeFirst(stopped.count - 32) }
        return activeID == id
    }

    func finish() { activeID = nil }
}
