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
