import io
import wave
from adex_tools.media import image_fixture, audio_fixture
from adex_tools.research import public_url
from adex_tools.calendar import calendar_object
import pytest
from fastapi import HTTPException


def test_deterministic_licensed_fixtures():
    assert image_fixture() == image_fixture()
    assert image_fixture().startswith(b"\x89PNG")
    with wave.open(io.BytesIO(audio_fixture())) as audio:
        assert audio.getnframes() / audio.getframerate() == 3


def test_input_urls_are_restricted():
    assert public_url("https://example.com/report")
    for url in [
        "http://example.com",
        "https://127.0.0.1",
        "https://169.254.169.254",
        "https://localhost",
        "https://name.internal",
        "https://user:password@example.com",
        "https://example.com:8443",
    ]:
        assert not public_url(url)


def test_calendar_text_cannot_inject_components():
    output = calendar_object(
        {
            "title": "Hello\nEND:VEVENT",
            "start": "2026-10-12T10:00:00+08:00",
            "end": "2026-10-12T11:00:00+08:00",
        },
        "fixed",
    )
    assert output.count("\r\nEND:VEVENT") == 1
    assert "DTSTART:20261012T020000Z" in output
    with pytest.raises(HTTPException):
        calendar_object(
            {"title": "Invalid", "start": "2026-10-12T10:00:00", "end": "2026-10-12T11:00:00"}, "fixed"
        )


def test_webhook_signature_and_expiration():
    import hashlib, hmac, time
    from adex_tools.webhooks import verify_signature

    key = "test-webhook-secret"
    timestamp = str(int(time.time()))
    body = b'{"event_id":"fixture"}'
    signature = hmac.new(key.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    verify_signature(key, timestamp, body, signature)
    with pytest.raises(HTTPException):
        verify_signature(key, timestamp, body + b"changed", signature)
    with pytest.raises(HTTPException):
        verify_signature(key, "1", body, signature)


async def test_music_adapter_payload_real_audio_and_no_replay(monkeypatch):
    import httpx
    from adex_tools.minimax_music import MiniMaxMusicProvider
    monkeypatch.setenv('ADEX_MUSIC_API_KEY','fixture-key')
    requests=[]
    def handle(request):
        import json
        requests.append(json.loads(request.content))
        return httpx.Response(200,json={'base_resp':{'status_code':0},'trace_id':'fixture-trace','data':{'audio':b'ID3fixture'.hex()},'extra_info':{'music_duration':180000}})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handle)))
    provider=MiniMaxMusicProvider()
    result=await provider.submit(kind='AUDIO',prompt='浪漫放松原创钢琴',input_refs=[],params={'duration_seconds':180},request_key='stable')
    audio,name,mime=await provider.get_result(provider_job_id=result['provider_job_id'])
    assert audio==b'ID3fixture' and mime=='audio/mpeg'
    assert requests[0]['is_instrumental'] and '180' in requests[0]['prompt']
    assert (await provider.reconcile(request_key='stable',provider_job_id=result['provider_job_id']))['status']=='UNKNOWN'
    assert len(requests)==1


async def test_music_adapter_rejects_denied_provider(monkeypatch):
    import httpx
    from adex_tools.minimax_music import MiniMaxMusicProvider
    monkeypatch.setenv('ADEX_MUSIC_API_KEY','fixture-key')
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'base_resp':{'status_code':1004,'status_msg':'secret account'}}))))
    with pytest.raises(HTTPException,match='MUSIC_PROVIDER_DENIED'):
        await MiniMaxMusicProvider().submit(kind='AUDIO',prompt='relax',input_refs=[],params={},request_key='stable')


async def test_acestep_music_job_recovery_and_private_audio(monkeypatch):
    import httpx
    import json
    from adex_tools.acestep_music import AceStepMusicProvider
    requests=[]
    def handle(request):
        requests.append(request)
        if request.url.path=='/release_task':
            payload=json.loads(request.content)
            assert payload['audio_duration']==180 and payload['batch_size']==1
            assert payload['lyrics']=='[Instrumental]' and not payload['thinking']
            return httpx.Response(200,json={'code':200,'data':{'task_id':'job-1'}})
        if request.url.path=='/query_result':
            return httpx.Response(200,json={'code':200,'data':[{'task_id':'job-1','status':1,'result':json.dumps([{'file':'/v1/audio?path=private.mp3','metas':{'duration':180}}])}]})
        return httpx.Response(200,content=b'ID3original-fixture')
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handle)))
    provider=AceStepMusicProvider()
    receipt=await provider.submit(kind='AUDIO',prompt='romantic piano',input_refs=[],params={'duration_seconds':180},request_key='stable')
    # New adapter instance queries the recorded remote job, without submitting twice.
    recovered=AceStepMusicProvider()
    assert (await recovered.reconcile(request_key='stable',provider_job_id=receipt['provider_job_id']))['status']=='SUCCEEDED'
    audio,_,mime=await recovered.get_result(provider_job_id=receipt['provider_job_id'])
    assert audio==b'ID3original-fixture' and mime=='audio/mpeg'
    assert recovered.metadata['music_duration']==180000
    assert len([r for r in requests if r.url.path=='/release_task'])==1


def test_acestep_runner_rejects_remote_url(monkeypatch):
    from adex_tools.acestep_music import AceStepMusicProvider
    monkeypatch.setenv('ADEX_ACESTEP_URL','http://untrusted.example')
    with pytest.raises(HTTPException,match='MUSIC_RUNNER_CONFIGURATION_INVALID'):
        AceStepMusicProvider()


async def test_dashscope_video_recovers_job_without_resubmit(monkeypatch):
    import httpx,json
    from adex_tools.dashscope_media import DashScopeMediaProvider
    monkeypatch.setenv('DASHSCOPE_API_KEY','fixture-key')
    calls=[]
    def handle(request):
        calls.append(request)
        if request.url.path.endswith('/video-synthesis'):
            body=json.loads(request.content)
            assert body['model']=='wan3.0-video' and body['parameters']['duration']==5
            assert request.headers['X-DashScope-Async']=='enable'
            return httpx.Response(200,json={'output':{'task_id':'job1','task_status':'PENDING'}})
        if request.url.path.endswith('/tasks/job1'):
            return httpx.Response(200,json={'output':{'task_status':'SUCCEEDED','video_url':'https://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/generated.mp4'}})
        assert 'Authorization' not in request.headers
        return httpx.Response(200,content=b'\0\0\0\x18ftypisomxxxx')
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handle)))
    receipt=await DashScopeMediaProvider('VIDEO').submit(kind='VIDEO',prompt='cat',input_refs=[],params={'duration_seconds':5},request_key='stable')
    recovered=DashScopeMediaProvider('VIDEO')
    assert (await recovered.reconcile(request_key='stable',provider_job_id=receipt['provider_job_id']))['status']=='SUCCEEDED'
    data,_,mime=await recovered.get_result(provider_job_id='job1')
    assert mime=='video/mp4' and data[4:8]==b'ftyp'
    assert len([r for r in calls if r.method=='POST'])==1


async def test_dashscope_music_permission_denied_is_not_success(monkeypatch):
    import httpx
    from adex_tools.dashscope_media import DashScopeMediaProvider
    monkeypatch.setenv('DASHSCOPE_API_KEY','fixture-key')
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(lambda r:httpx.Response(403,json={'code':'AccessDenied'}))))
    with pytest.raises(HTTPException,match='MEDIA_PROVIDER_ACCESS_DENIED'):
        await DashScopeMediaProvider('AUDIO').submit(kind='AUDIO',prompt='romantic piano',input_refs=[],params={},request_key='stable')


async def test_qwen_music_duration_and_private_download(monkeypatch):
    import httpx,json
    from adex_tools.dashscope_media import DashScopeMediaProvider
    monkeypatch.setenv('DASHSCOPE_API_KEY','fixture-key')
    monkeypatch.setenv('DASHSCOPE_MUSIC_MODEL','qwen-audio-3.1-tts-next')
    calls=[]
    def handle(request):
        calls.append(request)
        if request.method=='POST':
            assert request.url.path.endswith('/tts/SpeechSynthesizer')
            body=json.loads(request.content)
            assert '30' in body['input']['text_prompt'] and body['input']['format']=='mp3'
            return httpx.Response(200,json={'request_id':'audio1','output':{'audio':{'url':'https://result.aliyuncs.com/music.mp3','duration':29.8}}})
        assert 'Authorization' not in request.headers
        return httpx.Response(200,content=b'ID3fixture')
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handle)))
    provider=DashScopeMediaProvider('AUDIO')
    with pytest.raises(HTTPException,match='MUSIC_DURATION_UNSUPPORTED'):
        await provider.submit(kind='AUDIO',prompt='piano',input_refs=[],params={'duration_seconds':180},request_key='long')
    assert not calls
    receipt=await provider.submit(kind='AUDIO',prompt='piano',input_refs=[],params={'duration_seconds':30},request_key='one')
    data,_,mime=await provider.get_result(provider_job_id=receipt['provider_job_id'])
    assert mime=='audio/mpeg' and data==b'ID3fixture' and provider.metadata['music_duration']==29800
    assert len(calls)==2


@pytest.mark.parametrize('duration',[121,180,240,600])
def test_composition_sections_fit_provider_limit(duration):
    from adex_tools.music_composition import section_durations
    sections=section_durations(duration)
    assert all(2 < part <= 120 for part in sections)
    assert sum(sections)-2*(len(sections)-1)==pytest.approx(duration)


async def test_original_music_crossfade_has_expected_duration():
    import asyncio,tempfile
    from pathlib import Path
    from adex_tools.music_composition import join_sections
    sections=[]
    with tempfile.TemporaryDirectory() as directory:
        for index,frequency in enumerate([440,660]):
            path=Path(directory)/f'{index}.mp3'
            process=await asyncio.create_subprocess_exec('ffmpeg','-nostdin','-v','error','-f','lavfi','-i',f'sine=frequency={frequency}:duration=4','-c:a','libmp3lame',str(path))
            assert await process.wait()==0
            sections.append(path.read_bytes())
    data,duration=await join_sections(sections)
    assert data.startswith(b'ID3') and 5900<duration<6300


async def test_music_composition_resume_reuses_stable_child_keys(monkeypatch):
    import os,httpx
    from adex_tools import creative
    from adex_tools.music_composition import MusicCompositionProvider
    calls=[]
    async def generate(core,owner,body,**kw):
        assert kw=={'composition_part':True}
        assert body['params']['duration_seconds']<=120
        calls.append(body['request_key'])
        return {'artifact':{'file_id':'part-file'}}
    monkeypatch.setattr(creative,'generate',generate)
    async def join(parts):return b'ID3full',180000
    monkeypatch.setattr('adex_tools.music_composition.join_sections',join)
    monkeypatch.setenv('ADEX_APP_URL','http://app')
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=b'ID3part'))))
    class Core:
        def token(self,*args):return 'scoped-fixture'
    body={'request_key':'stable','prompt':'piano','params':{'duration_seconds':180},'kind':'AUDIO','provider':'dashscope','rights_confirmed':True}
    first=MusicCompositionProvider(Core(),'owner',body)
    receipt=await first.submit()
    assert not calls
    resumed=MusicCompositionProvider(Core(),'owner',body)
    await resumed.reconcile(request_key='stable',provider_job_id=receipt['provider_job_id'])
    data,_,mime=await resumed.get_result(provider_job_id=receipt['provider_job_id'])
    assert calls==['stable:section:0','stable:section:1'] and mime=='audio/mpeg' and data==b'ID3full'
    assert resumed.metadata['music_duration']==180000


async def test_unknown_composition_section_stops_without_later_submission(monkeypatch):
    from adex_tools import creative
    from adex_tools.music_composition import MusicCompositionProvider
    calls=[]
    async def unknown(core,owner,body,**kw):
        calls.append(body['request_key'])
        raise HTTPException(409,'PROVIDER_UNKNOWN')
    monkeypatch.setattr(creative,'generate',unknown)
    provider=MusicCompositionProvider(object(),'owner',{'request_key':'stable','prompt':'piano','params':{'duration_seconds':180}})
    with pytest.raises(HTTPException,match='PROVIDER_UNKNOWN'):
        await provider.get_result(provider_job_id=provider.job_id)
    assert calls==['stable:section:0']
