"""Local operator setup; binds this Mac to one existing account. No OS permission changes."""

import argparse
import os
from pathlib import Path
import psycopg
from config import load, ROOT

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--enable", action="store_true", required=True)
parser.add_argument(
    "--owner", help="Existing local account; defaults to configured owner"
)
parser.add_argument(
    "--all-apps",
    action="store_true",
    help="Authorize the bound owner to operate all installed Mac applications",
)
parser.add_argument("--desktop-files", action="store_true", help="Explicitly permit returning Desktop documents to this owner")
args = parser.parse_args()
e = load()
owner = args.owner or e["ADEX_OWNER_USERNAME"]
with psycopg.connect(
    host=e["ADEX_PG_HOST"],
    port=e["ADEX_PG_PORT"],
    dbname=e["ADEX_PG_DB"],
    user="adex_admin",
    password=e["ADEX_ADMIN_PASSWORD"],
) as c:
    row = c.execute(
        "SELECT id FROM app.users WHERE username=%s AND NOT is_guest", (owner,)
    ).fetchone()
if not row:
    raise SystemExit("Existing non-guest owner required")
binary = ROOT / ".local-data/computer-runner/AdexComputerRunner"
if not binary.is_file():
    raise SystemExit("Run scripts/build_computer_runner.py first")
values = {
    "ADEX_COMPUTER_ENABLED": "true",
    "ADEX_COMPUTER_FILE_ROOTS": str(Path.home() / "Desktop") if args.desktop_files else e.get("ADEX_COMPUTER_FILE_ROOTS", ""),
    "ADEX_COMPUTER_APP_POLICY": "all_installed" if args.all_apps else "allowlist",
    "ADEX_COMPUTER_OWNER_ID": str(row[0]),
    "ADEX_COMPUTER_RUNNER": str(binary),
    "ADEX_COMPUTER_HOST_ID": "local-mac",
    "ADEX_COMPUTER_APPS": "计算器=com.apple.calculator,Calculator=com.apple.calculator,文本编辑=com.apple.TextEdit,TextEdit=com.apple.TextEdit,Chrome=com.google.Chrome,Google Chrome=com.google.Chrome,谷歌浏览器=com.google.Chrome,Chrome浏览器=com.google.Chrome",
}
p = ROOT / ".env"
lines = p.read_text().splitlines()
lines = [line for line in lines if line.split("=", 1)[0] not in values]
p.write_text("\n".join([*lines, *[k + "=" + v for k, v in values.items()]]) + "\n")
os.chmod(p, 0o600)
print(
    "Configured one existing owner; application policy: "
    + values["ADEX_COMPUTER_APP_POLICY"]
    + ". OS Accessibility authorization still required."
)
