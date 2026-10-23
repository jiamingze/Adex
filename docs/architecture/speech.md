# Streaming speech recognition

Clients capture 16 kHz mono signed little-endian PCM16. Web recognition uses Alibaba Cloud
`qwen3-asr-flash-realtime` in Tools. On already-authorized iPhones with on-device Chinese
recognition, local text takes priority so the accurate displayed utterance is not
overwritten by a different cloud interpretation. Alibaba covers unavailable local ASR.
Microphone permission remains an OS responsibility.

App authenticates `POST /api/v1/speech/session` and returns a session UUID and a scoped
180-second capability. The client opens same-origin `/speech-ws/{session_id}`, sends
`{"token":"..."}` as its first frame (never URL), then binary PCM frames (<=32 KiB).
It sends `{"type":"finish"}` on release, or closes the socket on cancellation.
Tools replies `ready`, `partial` with cumulative `text`, `final` with authoritative
`text`, or `error` with a bounded code. No provider events/credentials are exposed.

Tools migration 010 records consumed session IDs (one use, three-minute retention
minimum) and active owner leases. A PostgreSQL advisory lock serializes the per-owner
claim. Limit one active stream per owner, 45 seconds capture, 15 seconds finalize,
1.44 MB audio. All connections close on cancellation/error/timeout. Disconnection
cannot produce a successful final result. Raw audio and transcripts stay in memory;
no media files or transcript logging. PostgreSQL outage fails closed. This is an
ephemeral ASR connection lease, not a second background scheduler/recovery system.

Existing hold/release/slide-cancel and haptic behavior are preserved. Permission/start
races are guarded by gesture identity; release before capture must never start a mic.
Real provider verification uses synthetic speech; mocked tests prove protocol behavior
only. Missing/rejected credentials are BLOCKED_EXTERNAL, never a fake recognition.

Deployment must proxy WebSocket upgrades for `/speech-ws/` to Tools. All other Tools
routes stay internal. Configure `ADEX_ASR_MODEL`, `ADEX_ASR_WS_URL`, `DASHSCOPE_API_KEY`
in Tools only. Use TLS for any non-local entry point. No schema migration in App.


### Verification and rollout

1. Apply migrations: `uv run python scripts/migrate.py`; configure the existing
   private DashScope key and restart App/Tools plus gateway after building.
2. `make format build test check-style test-ios-speech`.
3. `uv run python scripts/test_stack.py tests/integration/test_speech.py -q`
   (isolated database; no real ASR). To verify paid external recognition explicitly:
   `ADEX_TEST_REAL_ASR=1 uv run python scripts/test_stack.py tests/integration/test_speech.py -q`.
   This uses macOS `say` with invented speech, not the user's microphone.
4. Build/bundle iOS using the existing installation guide. Smoke-test microphone
   authorization, hold/release, live text, slide cancellation and backgrounding on device.
5. If unavailable, check Tools readiness/PG, gateway WebSocket upgrade and Alibaba
   account/model availability. Never put the long-lived provider key in a client or URL.

Provider references: [Alibaba realtime guide](https://help.aliyun.com/zh/model-studio/real-time-speech-recognition-user-guide),
[client events](https://help.aliyun.com/en/model-studio/qwen-asr-realtime-client-events),
[server events](https://help.aliyun.com/en/model-studio/qwen-asr-realtime-server-events).

### Capture before network readiness

Microphone capture begins on the held gesture, concurrently with authenticated session
creation. PCM is queued only in client memory (bounded to the existing 45-second
budget) until the provider is ready. Releasing after capture stops the microphone
immediately but preserves the queued utterance until upload and provider finalization;
release/cancel while microphone permission is pending prevents late recording.
Cancellation discards the queue and closes the connection. Network setup must never
silently erase already captured speech. Lifecycle logs contain frame/byte counts and
bounded error categories only, never audio, transcript, API keys or bearer tickets.

### Native iOS streaming

iOS sends microphone PCM directly through a native URLSession WebSocket, using the
same App-issued scoped ticket and Tools relay. PCM no longer traverses the WebView
JavaScript bridge on every audio buffer; only transcript/status events cross it.
A serial, bounded queue preserves audio/finish ordering during handshake and touch
tracking. Browser capture retains the shared JS transport. All credential, duration,
release/cancel and server final-result rules remain the same.


### Consistent displayed and submitted text

After actual iPhone feedback, the source-selection policy is local-first on iOS.
Already-authorized, explicitly on-device-only Chinese recognition supplies interim
text and the submitted utterance. After release, allow up to 800 ms for its final tail;
use the last nonempty local draft if a final result does not arrive. A cloud result
must never overwrite this text. When no local text is available, use Alibaba's final
transcript instead. The native cloud stream may run concurrently for fallback readiness;
it is not selected when usable local text exists. No Apple cloud fallback and no forced extra permission dialog.
The released panel stays frozen while finalization completes; intermediate cloud
prefixes are not replayed into it. Each gesture owns a fresh selection state and
cancellation settles once. This intentionally supersedes the earlier cloud-final policy.


Native selection regression: `make test-ios-speech-choice` verifies accurate local text
wins even if a differing cloud result arrives first or later; no usable local text falls
back to the cloud. This encodes actual iPhone feedback, rather than assuming the cloud
is always more accurate. `make test-ios-speech-stream` separately tests cancellation.
