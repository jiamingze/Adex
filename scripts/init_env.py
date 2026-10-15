import base64
import secrets
from config import ROOT

path = ROOT / ".env"
if path.exists():
    raise SystemExit("Existing .env preserved.")
values = {
    "ADEX_OWNER_USERNAME": "owner",
    "ADEX_RUNNER_KEY": secrets.token_urlsafe(48),
    "ADEX_BROWSER_ENCRYPTION_KEY": base64.b64encode(secrets.token_bytes(32)).decode(),
    "TAVILY_API_KEY": "",
    "ADEX_OWNER_PASSWORD": secrets.token_urlsafe(18),
    "ADEX_ADMIN_PASSWORD": secrets.token_urlsafe(32),
    "ADEX_MODEL_PROVIDER": "minimax",
    "MINIMAX_API_KEY": "",
    "MINIMAX_BASE_URL": "https://api.minimaxi.com/v1",
    "MINIMAX_MODEL": "MiniMax-M2.5",
    "ADEX_MAX_OUTPUT_TOKENS": "4096",
    "ADEX_BACKGROUND_WORKER": "true",
    "ADEX_PG_HOST": "127.0.0.1",
    "ADEX_PG_PORT": "55432",
    "ADEX_PG_DB": "adex_dev",
    "ADEX_REDIS_URL": "redis://127.0.0.1:56379/0",
    "ADEX_FILE_STORAGE_ROOT": str(ROOT / ".local-data/files"),
}
for name, port in [
    ("APP", 8080),
    ("AUTOMATION", 8081),
    ("AGENT", 8105),
    ("TOOLS", 8107),
]:
    values["ADEX_" + name + "_KEY"] = secrets.token_urlsafe(48)
    values["ADEX_" + name + "_DB_PASSWORD"] = secrets.token_urlsafe(32)
    values["ADEX_" + name + "_URL"] = f"http://127.0.0.1:{port}"
path.write_text("".join(k + "=" + v + "\n" for k, v in values.items()))
path.chmod(0o600)
print("Created private .env. Owner login credentials are stored there.")
