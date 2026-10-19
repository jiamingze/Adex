"""Real App/PG organization with deterministic model fixtures, never external execution."""
from uuid import uuid4
import httpx
from test_reliability import client


def test_goal_publishes_real_tasks_idempotently_and_tracks_progress(client):
    body = {'id': str(uuid4()), 'title': '准备产品发布', 'outcome': '完成可验证的发布清单',
            'steps': ['整理说明', '验证安装']}
    created = client.post('/api/v1/goals', json=body)
    created.raise_for_status()
    goal = created.json()
    assert goal['total'] == 2 and goal['done'] == 0
    assert client.post('/api/v1/goals', json=body).json()['id'] == goal['id']
    assert client.post('/api/v1/goals', json={**body, 'title': 'changed'}).status_code == 409
    task = goal['tasks'][0]
    assert task['important'] and not task['urgent']
    update = client.patch('/api/v1/matrix/' + task['id'], json={**task, 'status': 'DONE'})
    update.raise_for_status()
    goal = next(g for g in client.get('/api/v1/goals').json()['items'] if g['id'] == goal['id'])
    assert goal['done'] == 1 and goal['total'] == 2
    patch = {'title': goal['title'], 'outcome': goal['outcome'], 'status': 'ARCHIVED', 'revision': goal['revision']}
    assert client.patch('/api/v1/goals/' + goal['id'], json=patch).status_code == 200
    assert client.patch('/api/v1/goals/' + goal['id'], json=patch).status_code == 409
    assert any(t['id'] == task['id'] for t in client.get('/api/v1/matrix').json()['items'])
    name = 'goal-' + str(uuid4())[:10]
    with httpx.Client(base_url=str(client.base_url), trust_env=False) as other:
        other.post('/api/v1/auth/register', json={'username': name, 'password': 'test'}).raise_for_status()
        assert other.patch('/api/v1/goals/' + goal['id'], json=patch).status_code == 404
        assert other.post('/api/v1/goals', json=body).status_code == 404
        assert not other.get('/api/v1/goals').json()['items']


def test_goal_plan_is_only_a_proposal_and_invalid_steps_do_not_publish(client):
    before = client.get('/api/v1/goals').json()
    proposal = client.post('/api/v1/goals/plan', json={'request_id': str(uuid4()), 'title': '准备发布', 'outcome': '完成文档与验证'})
    proposal.raise_for_status()
    assert client.get('/api/v1/goals').json() == before
    assert proposal.json()['steps']
    assert proposal.json()['provider'] == 'mock'
    bad = client.post('/api/v1/goals', json={'id': str(uuid4()), 'title': '测试', 'outcome': '', 'steps': ['ok', 123]})
    assert bad.status_code == 400


def test_goal_context_is_owned_current_and_excludes_archived_goals(client):
    from test_reliability import sign
    goal = client.post('/api/v1/goals', json={'id': str(uuid4()), 'title': '目标上下文 TEST_FIXTURE', 'outcome': '真实进度', 'steps': ['完成验证']}).json()
    conv = client.post('/api/v1/conversations', json={'title': 'goal context fixture'}).json()['id']
    client.post(f'/api/v1/conversations/{conv}/messages', json={'client_message_id': str(uuid4()), 'content': '我的目标进展如何'}).raise_for_status()
    owner = client.get('/api/v1/me').json()['id']
    headers = sign('agent', 'app', 'context:read', owner, conv)
    context = client.get(f'/internal/context/{conv}', headers=headers).json()
    observed = next(g for g in context['goals'] if g['id'] == goal['id'])
    assert observed['done'] == 0 and observed['total'] == 1
    client.patch('/api/v1/goals/' + goal['id'], json={**goal, 'status': 'ARCHIVED'}).raise_for_status()
    context = client.get(f'/internal/context/{conv}', headers=headers).json()
    assert not any(g['id'] == goal['id'] for g in context['goals'])
