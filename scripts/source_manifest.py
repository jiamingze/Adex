"""Record source hashes without ignored credentials, runtime files or user data."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / 'docs/VALIDATION_MANIFEST.json'
paths = subprocess.check_output(['rg', '--files', '-g', '!docs/VALIDATION_MANIFEST.json'], cwd=ROOT, text=True).splitlines()
hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sorted(paths) if (ROOT / name).is_file()}
source_sha = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
target.write_text(json.dumps({'created_at_utc': datetime.now(timezone.utc).isoformat(), 'git_commit': None, 'source_tree_sha256': source_sha, 'files': hashes}, indent=2) + '\n')
print('Source manifest written:', len(hashes), 'files; tree SHA-256', source_sha)
