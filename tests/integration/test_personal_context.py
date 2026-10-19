"""Owner-scoped read projections, real isolated PostgreSQL; no external execution."""
from uuid import uuid4
from test_reliability import client, db, sign


def test_chat_reads_current_tasks_and_notes_without_creating_memory(client):
    task = client.post('/api/v1/matrix', json={'title': '上下文隔离 TEST_FIXTURE', 'important': True, 'urgent': False, 'status': 'TODO'}).json()
    note = client.post('/api/v1/notes', json={'id': str(uuid4()), 'title': '方案 TEST_FIXTURE', 'content': '只读资料内容', 'pinned': False, 'revision': 0}).json()
    conv = client.post('/api/v1/conversations', json={'title': 'context fixture'}).json()['id']
    client.post(f'/api/v1/conversations/{conv}/messages', json={'client_message_id': str(uuid4()), 'content': '结合我的待办和笔记安排今天'}).raise_for_status()
    owner = client.get('/api/v1/me').json()['id']
    headers = sign('agent', 'app', 'context:read', owner, conv)
    projection = client.get(f'/internal/context/{conv}', headers=headers).json()['personal_context']
    assert any(t['id'] == task['id'] for t in projection['tasks'])
    assert any(n['id'] == note['id'] for n in projection['notes'])
    assert len(projection['tasks']) <= 20 and len(projection['notes']) <= 8
    assert projection['read_only'] is True
    client.delete(f"/api/v1/notes/{note['id']}?revision={note['revision']}").raise_for_status()
    projection = client.get(f'/internal/context/{conv}', headers=headers).json()['personal_context']
    assert not any(n['id'] == note['id'] for n in projection['notes'])


def test_native_calendar_hash_retry_cleanup_and_owner_boundary(client, db):
    from datetime import datetime, timezone
    from test_reliability import wait
    conv = client.post('/api/v1/conversations', json={'title': 'calendar bridge fixture'}).json()['id']
    observation = {'source': 'device', 'observed_at': datetime.now(timezone.utc).isoformat(), 'timezone': 'Asia/Shanghai', 'partial': False, 'events': []}
    body = {'client_message_id': str(uuid4()), 'content': '看看我的会议安排', 'client_calendar': observation}
    result = client.post(f'/api/v1/conversations/{conv}/messages', json=body)
    result.raise_for_status()
    turn = result.json()['message_id']
    wait(lambda: db.execute('SELECT status FROM app.turns WHERE id=%s', (turn,)).fetchone()['status'] in ('COMPLETED', 'FAILED'))
    row = db.execute('SELECT client_calendar,calendar_hash FROM app.turns WHERE id=%s', (turn,)).fetchone()
    assert row['client_calendar'] is None and row['calendar_hash']
    assert client.post(f'/api/v1/conversations/{conv}/messages', json=body).status_code == 200
    changed = {**body, 'client_calendar': {**observation, 'partial': True}}
    assert client.post(f'/api/v1/conversations/{conv}/messages', json=changed).status_code == 409
    wrong_owner = str(uuid4())
    assert client.get(f'/internal/context/{conv}', headers=sign('agent','app','context:read',wrong_owner,conv)).status_code == 404
    bad = {**body, 'client_message_id': str(uuid4()), 'client_calendar': {**observation, 'events': [{}]}}
    assert client.post(f'/api/v1/conversations/{conv}/messages', json=bad).status_code == 400
