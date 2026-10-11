"""Backup local development PG and App-owned disk with checksums; no production credentials."""

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from config import load, ROOT

e = load()
if any(
    (ROOT / ".local-data" / (name + ".pid")).exists()
    for name in ("app", "automation", "agent", "tools")
):
    raise SystemExit(
        "Stop business services with make down-dev before taking a consistent local backup."
    )
folder = (
    ROOT / ".local-data/backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
)
folder.mkdir(parents=True)
bin_ = "/opt/homebrew/opt/postgresql@16/bin/pg_dump"
if not Path(bin_).exists():
    bin_ = "pg_dump"
env = dict(e)
env["PGPASSWORD"] = e["ADEX_ADMIN_PASSWORD"]
subprocess.run(
    [
        bin_,
        "-h",
        e["ADEX_PG_HOST"],
        "-p",
        e["ADEX_PG_PORT"],
        "-U",
        "adex_admin",
        "-d",
        e["ADEX_PG_DB"],
        "-Fc",
        "-f",
        str(folder / "database.dump"),
    ],
    env=env,
    check=True,
)
files = Path(e["ADEX_FILE_STORAGE_ROOT"])
shutil.copytree(files, folder / "files")
manifest = {
    str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in folder.rglob("*")
    if p.is_file()
}
(folder / "manifest.json").write_text(json.dumps(manifest, indent=2))
folder.chmod(0o700)
print("Backup created:", folder)
print(
    "Local copy is not disaster recovery; copy encrypted backup off-host before release."
)
