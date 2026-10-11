"""Opt-in isolated Compose acceptance; never targets the user's native database."""
import hashlib
import os
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
validation = ROOT / '.local-data/compose-validation.env'
cfg = dict(line.split('=', 1) for line in validation.read_text().splitlines() if line and not line.startswith('#'))
assert cfg['ADEX_PG_DB'] == 'adex_container_acceptance'
env = dict(os.environ)
if (ROOT / '.local-data/docker-config').exists():
    env.setdefault('DOCKER_CONFIG', str(ROOT / '.local-data/docker-config'))
colima = Path.home() / '.colima/adex/docker.sock'
if colima.exists():
    env.setdefault('DOCKER_HOST', 'unix://' + str(colima))
compose = ['docker', 'compose', '--env-file', str(validation), '-p', 'adex-acceptance', '-f', 'deploy/compose/compose.yaml', '-f', 'deploy/compose/compose.runner.yaml', '-f', '.local-data/compose-images.yaml']

def wait(fn, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = fn()
            if result:
                return result
        except httpx.HTTPError:
            pass
        time.sleep(.3)
    raise AssertionError('Compose readiness deadline exceeded')

base = 'http://127.0.0.1:' + cfg['ADEX_WEB_PORT']
with httpx.Client(base_url=base, trust_env=False, timeout=25) as client:
    wait(lambda: client.get('/health/ready').status_code == 200)
    login = client.post('/api/v1/auth/login', json={'username': cfg['ADEX_OWNER_USERNAME'], 'password': cfg['ADEX_OWNER_PASSWORD']})
    login.raise_for_status()
    client.headers['Authorization'] = 'Bearer ' + login.json()['token']
    conv = client.post('/api/v1/conversations', json={'title': 'Compose isolated acceptance'}).json()['id']
    client.post(f'/api/v1/conversations/{conv}/messages', json={'content': 'Compose durable chat fixture', 'client_message_id': str(uuid4())}).raise_for_status()
    messages = wait(lambda: (lambda data: data if any(m['role'] == 'assistant' and m['content'] for m in data['items']) else None)(client.get(f'/api/v1/conversations/{conv}/messages').json()))
    body = b'Compose private durable file fixture'
    upload = client.post('/api/v1/files', files={'file': ('compose.txt', body, 'text/plain')}, headers={'Idempotency-Key': str(uuid4())})
    upload.raise_for_status()
    file = upload.json()
    path = f"/api/v1/files/{file['id']}/content"
    assert client.get(path).content == body
    assert client.get(path, headers={'Range': 'bytes=0-6'}).status_code == 206
    assert httpx.get(base + path, trust_env=False).status_code == 401
    subprocess.run(compose + ['up', '-d', '--no-build', '--no-deps', '--force-recreate', 'adex-app'], cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
    wait(lambda: client.get('/health/ready').status_code == 200)
    persisted = client.get(path)
    persisted.raise_for_status()
    assert hashlib.sha256(persisted.content).hexdigest() == file['sha256']
    assert client.get(f'/api/v1/conversations/{conv}/messages').json()['items'] == messages['items']
    print('Compose mock chat / private Range / App recreation / PG + files persistence PASS')

probe = """
import asyncio,httpx
from adex_kernel.core import Core
async def main():
    for service,port in [('app',8080),('automation',8081),('agent',8105),('tools',8107)]:
        r=httpx.get(f'http://adex-{service}:{port}/health/ready',trust_env=False,timeout=5)
        r.raise_for_status()
    result=await Core('agent').call('tools','code:check','POST','/internal/game/check',{'source':'<html><body><canvas></canvas><p>Compose sandbox fixture</p></body></html>'})
    assert result['status']=='PASS' and result['has_canvas'],result
    print('Compose all services ready / signed isolated Runner PASS')
asyncio.run(main())
"""
subprocess.run(compose + ['exec','-T','adex-agent','/workspace/services/adex-agent/.venv/bin/python','-c',probe],cwd=ROOT,env=env,check=True)
