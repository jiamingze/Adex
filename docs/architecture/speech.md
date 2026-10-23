# Streaming speech recognition

Clients capture 16 kHz mono signed little-endian PCM16; recognition is performed by
Alibaba Cloud `qwen3-asr-flash-realtime` in Tools. Apple Speech and browser SpeechRecognition
are not fallback providers. Microphone permission remains an OS responsibility.

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
