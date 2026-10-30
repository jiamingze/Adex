import re
import hashlib
import json
import subprocess
from config import ROOT

files = subprocess.check_output(
    ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
    cwd=ROOT,
    text=True,
).splitlines()
patterns = [
    re.compile(r"sk-[A-Za-z0-9_-]{28,}"),
    re.compile(r"sk-api-[A-Za-z0-9_-]{25,}"),
    re.compile(r"tvly-[A-Za-z0-9_-]{20,}"),
    re.compile(r"GOCSPX-[A-Za-z0-9_-]{20,}"),
    re.compile(r"ya29\.[A-Za-z0-9._-]{30,}"),
    re.compile(r"-----BEGIN (?:EC |RSA )?PRIVATE KEY-----\s+[A-Za-z0-9+/=\r\n]{40,}"),
]
# Exact hashes only: audited upstream synthetic credentials and public test keys.
# Any local edit invalidates the exception and is scanned normally.
fixture_manifest = ROOT / "third_party/codex-public-test-fixtures.json"
fixtures = json.loads(fixture_manifest.read_text()) if fixture_manifest.exists() else {}
bad = []
for name in files:
    p = ROOT / name
    if p.is_file():
        if fixtures.get(name) == hashlib.sha256(p.read_bytes()).hexdigest():
            continue
        text = p.read_text(errors="replace")
        if any(pattern.search(text) for pattern in patterns):
            bad.append(name)
if bad:
    raise SystemExit("Credential pattern found in: " + ", ".join(bad))
assert (
    subprocess.run(["git", "check-ignore", "--quiet", ".env"], cwd=ROOT).returncode == 0
)
print("Secrets scan passed; .env excluded from Git.")
