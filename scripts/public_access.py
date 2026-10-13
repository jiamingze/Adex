"""Expose built Web + API through an account-free Cloudflare HTTPS tunnel."""
import argparse
import os
import re
import signal
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
state = root / '.local-data'
state.mkdir(exist_ok=True)
action = argparse.ArgumentParser()
action.add_argument('action', choices=['start', 'stop', 'status'])
mode = action.parse_args().action

def alive(name):
    file = state / (name + '.pid')
    if not file.exists(): return False
    try: os.kill(int(file.read_text()), 0); return True
    except ProcessLookupError: return False

def stop(name):
    file = state / (name + '.pid')
    if alive(name): os.killpg(int(file.read_text()), signal.SIGTERM)
    file.unlink(missing_ok=True)

def launch(name, command, cwd=root, env=None):
    with (state / (name + '.log')).open('w') as log:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=log, start_new_session=True)
    (state / (name + '.pid')).write_text(str(process.pid))

if mode == 'stop':
    stop('public-tunnel'); stop('public-web'); print('Public access stopped')
elif mode == 'status' or (alive('public-tunnel') and alive('public-web')):
    if alive('public-tunnel') and alive('public-web'):
        print((state / 'public-url.txt').read_text())
    else: print('Public access is not running')
else:
    if not (root / 'apps/web/dist/index.html').exists(): raise SystemExit('Build Web first: make build')
    stop('public-tunnel'); stop('public-web')
    launch('public-tunnel', ['cloudflared', 'tunnel', '--protocol', os.getenv('ADEX_TUNNEL_PROTOCOL', 'http2'), '--edge-ip-version', '4', '--url', 'http://127.0.0.1:4173', '--no-autoupdate'])
    url = None
    for _ in range(120):
        matches = re.findall(r'https://[a-z-]+\.trycloudflare\.com', (state / 'public-tunnel.log').read_text())
        if matches: url = matches[-1]; break
        if not alive('public-tunnel'): break
        time.sleep(.5)
    if not url:
        stop('public-tunnel'); raise SystemExit('Tunnel startup failed; inspect .local-data/public-tunnel.log')
    env = os.environ.copy()
    env['__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS'] = url.split('://')[1]
    launch('public-web', ['pnpm', 'exec', 'vite', 'preview', '--host', '127.0.0.1', '--port', '4173', '--strictPort'], root / 'apps/web', env)
    (state / 'public-url.txt').write_text(url)
    print(url)
