# Configuration

[中文](../zh-CN/configuration.md)

Run `uv run python scripts/init_env.py` once. Review `.env.example` for optional settings; it is a reference, not a deployable credential file. Keep `.env` private (0600). Never ship API keys in client builds or screenshots.

| Setting | Purpose |
| --- | --- |
| `ADEX_MODEL_PROVIDER` | `mock`, `minimax`, or `qwen` |
| `MINIMAX_API_KEY`, `MINIMAX_MODEL`, `MINIMAX_BASE_URL` | MiniMax chat credentials/model/endpoint |
| `DASHSCOPE_API_KEY`, `DASHSCOPE_CHAT_MODEL`, `DASHSCOPE_CHAT_BASE_URL` | Qwen compatible chat endpoint and model |
| `TAVILY_API_KEY` | Automatic web search |
| `ADEX_MUSIC_PROVIDER`, `ADEX_VIDEO_PROVIDER` | Select a configured media adapter, or `mock` |
| `DASHSCOPE_MUSIC_MODEL`, `DASHSCOPE_VIDEO_MODEL`, `DASHSCOPE_MEDIA_BASE_URL` | Alibaba media model and region endpoint |
| `ADEX_BACKGROUND_WORKER` | Enable persistent background execution |
| `ADEX_FILE_STORAGE_ROOT` | App-owned private local file directory |
| `ADEX_ES_URL` | Optional Elasticsearch indexing endpoint |
| `ADEX_ALLOWED_ORIGINS` | Exact trusted client origins, including native origin when used |
| `ADEX_IOS_API_URL` | Environment input to iOS preparation script; public HTTPS origin |

The model selector currently offers Qwen and MiniMax. Its configured model names must exist in your provider account and region; no key grants all modalities automatically. Current adapters include DashScope music/video, MiniMax music and local ACE-Step music. Inspect `services/adex-tools/src/adex_tools/creative.py` and provider modules before enabling a paid adapter. The default/mock path is intended for deterministic learning and tests.

SMTP and approved CalDAV integration are optional; consult `.env.example` and the provider integration checklist. Service signing keys and database passwords must be distinct. Configure budgets and storage quotas for your deployment. The initializer's random owner account differs from any developer's local private account.

Restart affected backend services after changing their environment. Rebuild iOS after changing the public API URL. Endpoint changes can affect reconciliation of existing provider jobs: do not switch providers mid-run without reviewing outstanding effects.

### Chat usage and browser reads

Set `ADEX_DAILY_MODEL_CALL_LIMIT=0` to remove the daily reply count limit while preserving usage accounting. Positive values enable a daily cap (the example defaults to 50). Search and creative media budgets remain independent.

Image requests use `ADEX_IMAGE_PROVIDER=dashscope` and `DASHSCOPE_IMAGE_MODEL=qwen-image-3.0`; use a Model Studio key and endpoint from the same region. Results are imported into private local file storage and displayed in the originating chat.

The read-only Chromium runner renders public HTTPS pages and bounded same-host links in an ephemeral, credential-free subprocess. Install with `uv run --project services/adex-tools playwright install chromium` (`--with-deps` on Linux). `ADEX_BROWSER_MODE=public` admits the requested public hostname; `allowlist` restricts requested destinations to exact `ADEX_BROWSER_ALLOWED_HOSTS`. In public mode those configured hosts also provide optional cross-origin assets. All DNS answers must be public; each run uses a CONNECT-only proxy pinned to admitted IPs, so private redirects and arbitrary ports are rejected. GET-only requests, no login/forms/downloads, at most three pages, two concurrent reads, bounded proxy connections/request counts and a 45-second child deadline. Reads receive no service credentials or browser profile. Sites requiring login, CAPTCHA, cross-host redirects or POST-based rendering may fail. See [browser architecture and verification](../architecture/browser-access.md).
