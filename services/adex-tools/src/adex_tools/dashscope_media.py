"""Alibaba original music and async Wan video. Never retry a submission."""
import asyncio
import os
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException


class DashScopeMediaProvider:
    def __init__(self, kind):
        self.kind = kind
        self.key = os.getenv('DASHSCOPE_API_KEY', '')
        self.base = os.getenv('DASHSCOPE_MEDIA_BASE_URL', 'https://dashscope.aliyuncs.com/api/v1').rstrip('/')
        endpoint = urlsplit(self.base)
        if not self.key or endpoint.scheme != 'https' or not (endpoint.hostname == 'dashscope.aliyuncs.com' or (endpoint.hostname or '').endswith('.cn-beijing.maas.aliyuncs.com')):
            raise HTTPException(503, 'MEDIA_NOT_CONFIGURED')
        self.model = os.getenv('DASHSCOPE_MUSIC_MODEL', 'fun-music-v1') if kind == 'AUDIO' else os.getenv('DASHSCOPE_VIDEO_MODEL', 'wan3.0-video')
        self.result = None
        self.metadata = {}

    async def request(self, method, path, payload=None):
        headers = {'Authorization': 'Bearer ' + self.key}
        if self.kind == 'VIDEO' and method == 'POST':
            headers['X-DashScope-Async'] = 'enable'
        async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=10), trust_env=False) as client:
            response = await client.request(method, self.base + path, json=payload, headers=headers)
            if response.status_code in (401, 403):
                raise HTTPException(503, 'MEDIA_PROVIDER_ACCESS_DENIED')
            if response.is_error:
                raise HTTPException(502, 'MEDIA_PROVIDER_REJECTED')
            value = response.json()
            if value.get('code'):
                raise HTTPException(502, 'MEDIA_PROVIDER_REJECTED')
            return value

    async def submit(self, *, kind, prompt, input_refs, params, request_key):
        if kind != self.kind or input_refs:
            raise HTTPException(400, 'UNSUPPORTED_CAPABILITY')
        if kind == 'AUDIO':
            duration = params.get('duration_seconds', 120)
            if self.model == 'qwen-audio-3.1-tts-next':
                if not isinstance(duration, (float, int)) or not 1 <= duration <= 120:
                    raise HTTPException(400, 'MUSIC_DURATION_UNSUPPORTED')
                mode = '原创歌曲，包含人声演唱' if params.get('mode') == 'vocals' else '原创纯音乐，没有说话、旁白或人声'
                value = await self.request('POST', '/services/audio/tts/SpeechSynthesizer', {
                    'model': self.model, 'input': {'text_prompt': f'【0.0s:{duration}s】{mode}。{prompt}。完整编曲、自然收尾。'[:3000],
                        'format': 'mp3', 'sample_rate': 48000, 'channels': 2},
                })
            else:
                value = await self.request('POST', '/services/audio/music/generation', {
                    'model': self.model, 'input': {'prompt': (prompt + f'。目标时长约{duration}秒。')[:2000],
                        'is_instrumental': params.get('mode', 'instrumental') != 'vocals', 'format': 'mp3'},
                })
            audio = value.get('output', {}).get('audio', {})
            if not audio.get('url') or not value.get('request_id'):
                raise HTTPException(502, 'MEDIA_RESULT_INVALID')
            self.result = audio['url']
            self.metadata['music_duration'] = audio.get('duration', value.get('usage', {}).get('duration', 0)) * 1000
            return {'provider_job_id': value['request_id'], 'status': 'SUCCEEDED'}
        duration = params.get('duration_seconds', 5)
        if not isinstance(duration, int) or not 2 <= duration <= 30:
            raise HTTPException(400, 'INVALID_MEDIA_DURATION')
        ratio = params.get('aspect_ratio', '16:9')
        if ratio not in ('21:9', '16:9', '4:3', '1:1', '3:4', '9:16'):
            raise HTTPException(400, 'INVALID_MEDIA_SIZE')
        value = await self.request('POST', '/services/aigc/video-generation/video-synthesis', {
            'model': self.model, 'input': {'prompt': prompt[:20000]},
            'parameters': {'duration': duration, 'resolution': '720P', 'ratio': ratio, 'audio': True},
        })
        return {'provider_job_id': value['output']['task_id'], 'status': value['output']['task_status']}

    async def reconcile(self, *, request_key, provider_job_id):
        if self.kind == 'AUDIO':
            return {'status': 'UNKNOWN', 'provider_job_id': provider_job_id}
        value = await self.request('GET', '/tasks/' + provider_job_id)
        output = value['output']
        if output['task_status'] == 'SUCCEEDED':
            self.result = output['video_url']
            return {'status': 'SUCCEEDED', 'provider_job_id': provider_job_id}
        if output['task_status'] in ('FAILED', 'CANCELED'):
            raise HTTPException(502, 'MEDIA_GENERATION_FAILED')
        return {'status': 'UNKNOWN', 'provider_job_id': provider_job_id}

    async def get_result(self, *, provider_job_id):
        deadline = asyncio.get_running_loop().time() + 900
        while self.result is None:
            await self.reconcile(request_key='', provider_job_id=provider_job_id)
            if self.result is not None:
                break
            if self.kind == 'AUDIO' or asyncio.get_running_loop().time() >= deadline:
                raise HTTPException(409, 'PROVIDER_UNKNOWN')
            await asyncio.sleep(3)
        url = urlsplit(self.result)
        # Only provider-owned storage; never follow arbitrary result redirects or attach credentials.
        if url.scheme not in ('http', 'https') or not (url.hostname or '').endswith('.aliyuncs.com') or url.username or url.password:
            raise HTTPException(502, 'MEDIA_RESULT_INVALID')
        secure_url = 'https://' + self.result.split('://', 1)[1]
        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            async with client.stream('GET', secure_url) as response:
                if response.is_error or response.is_redirect:
                    raise HTTPException(502, 'MEDIA_DOWNLOAD_FAILED')
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > (26 if self.kind == 'AUDIO' else 48) * 1024 * 1024:
                        raise HTTPException(502, 'MEDIA_OUTPUT_TOO_LARGE')
        if self.kind == 'AUDIO':
            if not (data.startswith(b'ID3') or (len(data) > 2 and data[0] == 255 and data[1] & 224 == 224)):
                raise HTTPException(502, 'MEDIA_RESULT_INVALID')
            return bytes(data), 'original-music.mp3', 'audio/mpeg'
        if len(data) < 12 or data[4:8] != b'ftyp':
            raise HTTPException(502, 'MEDIA_RESULT_INVALID')
        return bytes(data), 'generated-video.mp4', 'video/mp4'
