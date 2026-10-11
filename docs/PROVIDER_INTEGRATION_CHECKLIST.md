# Real Multimodal Provider Integration Checklist

The user will provide image / image-edit / music / video model APIs. This file is an onboarding contract, not a claim that access already exists. Never ask for or commit secrets in AGENTS.md, code, or developer tickets. Use environment/secret store references.

For each provider capture: provider name and documentation version, supported ECS regions and legal terms, base URL, authentication method, required headers, rate limits/quotas, capabilities and model IDs, prompt format, reference-image input method and maximum size, allowed aspect ratios/resolutions, music/video supported duration and codec, synchronous vs asynchronous job semantics, request idempotency support, provider job ID, status API, callback signing and retry policy, polling guidance, cancellation semantics, result download URL expiry, billing units, moderation and content rules.

### Deployment variables (placeholders, no real secrets)

```bash
ADEX_MEDIA_PROVIDER=mock
ADEX_MEDIA_API_BASE_URL= # supplied later
ADEX_MEDIA_API_TOKEN_FILE= # secret mounted only into Tools container
ADEX_MEDIA_CALLBACK_SECRET_FILE= # supplied later where supported
ADEX_MEDIA_DEFAULT_IMAGE_MODEL=
ADEX_MEDIA_DEFAULT_MUSIC_MODEL=
ADEX_MEDIA_DEFAULT_VIDEO_MODEL=
```

### Integration verification

1. Provider `/capabilities` adapter returns exact supported features and max values; unsupported features are disabled in UI without disabling other creative functions.
2. Signed callback verifies timestamp, HMAC/other documented signature scheme, dedupe and job ownership; unsigned callback MUST NOT mark success.
3. Submit with stable request key; interrupt network after submit; restore via `reconcile`; no blind duplicate generation.
4. Verify real output binary matches claimed format, duration/dimensions, audio/video playable on iPhone and browser.
5. Pull result into App-owned local persistent storage via private File API; verify sha256 and artifact provenance after restart.
6. Test budget/region failures, key rotation, rate limit, quota reached, invalid input file, cancelled provider job.
7. Keep real-model tests opt-in to avoid unexpected charges; if no API available status is `BLOCKED_EXTERNAL` and synthetic fixtures do not pass real-generation gate.
