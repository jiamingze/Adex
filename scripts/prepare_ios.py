"""Build a bundled iOS UI against the current public HTTPS API endpoint."""
import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse

root = Path(__file__).resolve().parents[1]
endpoint = os.environ.get('ADEX_IOS_API_URL')
if not endpoint:
    endpoint = (root / '.local-data/public-url.txt').read_text().strip()
parsed = urlparse(endpoint)
if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
    raise SystemExit('ADEX_IOS_API_URL must be a public HTTPS origin')
env = os.environ.copy()
env['VITE_ADEX_API_BASE'] = endpoint.rstrip('/')
subprocess.run(['pnpm', '--dir', 'apps/web', 'exec', 'tsc', '--noEmit'], cwd=root, env=env, check=True)
subprocess.run(['pnpm', '--dir', 'apps/web', 'exec', 'vite', 'build', '--outDir', '../ios/web-dist', '--emptyOutDir'], cwd=root, env=env, check=True)
subprocess.run(['pnpm', '--dir', 'apps/ios', 'sync'], cwd=root, check=True)
print('iOS bundled API:', env['VITE_ADEX_API_BASE'])
