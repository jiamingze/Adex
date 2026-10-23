import Foundation
let choice = SpeechTranscriptChoice()
choice.localAvailable = true
choice.preview("帮我安排明天下午的会议")
choice.cloud = "帮我安排明天下午的回忆"
precondition(choice.selection() == nil)
choice.released = true
precondition(choice.selection() == nil)
choice.localFinal("帮我安排明天下午的会议。")
precondition(choice.selection() == "帮我安排明天下午的会议。")
choice.cloud = "错误的后到结果"
precondition(choice.selection() == "帮我安排明天下午的会议。")
let fallback = SpeechTranscriptChoice()
fallback.released = true; fallback.cloud = "阿里云识别结果"
precondition(fallback.selection() == "阿里云识别结果")
let draft = SpeechTranscriptChoice()
draft.localAvailable = true; draft.preview("准确的已显示文字"); draft.released = true; draft.graceEnded = true
draft.cloudError = "SPEECH_CONNECTION_FAILED"
precondition(draft.selection() == "准确的已显示文字")
precondition(!draft.failed)
print("PASS: local final/draft wins, cloud fallback only without local text, no late overwrite")
