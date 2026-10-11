import os
from uuid import uuid4
import httpx


def test_guest_cookie_registration_preserves_private_owner():
    base=os.environ['ADEX_TEST_URL']
    with httpx.Client(base_url=base,trust_env=False) as a, httpx.Client(base_url=base,trust_env=False) as b:
        g=a.post('/api/v1/auth/guest');g.raise_for_status()
        assert g.json()['is_guest']
        assert 'HttpOnly' in g.headers['set-cookie'] and 'SameSite=Lax' in g.headers['set-cookie']
        first=a.get('/api/v1/me').json()['id']
        assert a.post('/api/v1/auth/guest').json()['token']==g.json()['token']
        conv=a.post('/api/v1/conversations',json={'title':'guest private'}).json()['id']
        b.post('/api/v1/auth/guest').raise_for_status()
        assert b.get(f'/api/v1/conversations/{conv}/messages').status_code==404
        assert a.patch('/api/v1/settings',json={'memory_enabled':True}).status_code==403
        assert a.post('/api/v1/conversations',json={'title':'csrf'},headers={'Origin':'https://evil.example'}).status_code==403
        assert a.post('/api/v1/auth/register',json={'username':'short','password':'short'}).status_code==400
        username='qa_'+uuid4().hex[:16]
        r=a.post('/api/v1/auth/register',json={'username':username,'password':'test-registration-2026'});r.raise_for_status()
        assert not r.json()['is_guest']
        assert a.get('/api/v1/me').json()['id']==first
        assert a.get(f'/api/v1/conversations/{conv}/messages').status_code==200
        assert b.post('/api/v1/auth/register',json={'username':username,'password':'another-password-2026'}).status_code==409
        assert b.get('/api/v1/me').json()['is_guest']
        assert a.post('/api/v1/auth/logout').status_code==200
        assert a.get('/api/v1/me').status_code==401
        a.post('/api/v1/auth/login',json={'username':username,'password':'test-registration-2026'}).raise_for_status()
        assert a.get(f'/api/v1/conversations/{conv}/messages').status_code==200


def test_guest_quota_applies_across_conversations():
    with httpx.Client(base_url=os.environ['ADEX_TEST_URL'],trust_env=False) as c:
        c.post('/api/v1/auth/guest').raise_for_status()
        for n in range(9):
            conv=c.post('/api/v1/conversations',json={'title':'quota'}).json()['id']
            response=c.post(f'/api/v1/conversations/{conv}/messages',json={'client_message_id':str(uuid4()),'content':'fixture hello'})
            assert response.status_code==(200 if n<8 else 429)
            if n==8:assert response.json()['code']=='GUEST_QUOTA_EXCEEDED'
