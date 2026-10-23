import Foundation

/// Keep the accurately displayed local utterance; cloud is a fallback, never an overwrite.
final class SpeechTranscriptChoice {
    var localAvailable = false
    private(set) var draft = ""
    private var finalLocal: String?
    var cloud: String?
    var cloudError: String?
    var released = false
    var graceEnded = false

    func preview(_ text: String) { if !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { draft = text } }
    func localFinal(_ text: String) { preview(text); if !text.isEmpty { finalLocal = text } }
    func selection() -> String? {
        guard released else { return nil }
        if let final = finalLocal { return final }
        if localAvailable && !graceEnded { return nil }
        if !draft.isEmpty { return draft }
        return cloud
    }
    var failed: Bool { released && (!localAvailable || graceEnded) && draft.isEmpty && cloud == nil && cloudError != nil }
}
