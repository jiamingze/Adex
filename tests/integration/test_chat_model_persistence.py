"""Model selector persistence contract against isolated real PostgreSQL; no live LLM claim."""
from uuid import uuid4
import pytest
from test_reliability import client, db


@pytest.mark.parametrize('model', ['qwen3.8-flash', 'qwen3.8-max', 'minimax', ''])
def test_supported_model_is_durably_saved_and_retry_is_idempotent(client, db, model):
    conv = client.post('/api/v1/conversations', json={'title': 'model persistence fixture'}).json()['id']
    body = {'content': 'TEST_FIXTURE model persistence', 'model': model, 'client_message_id': str(uuid4())}
    path = f'/api/v1/conversations/{conv}/messages'
    first = client.post(path, json=body)
    first.raise_for_status()
    retry = client.post(path, json=body)
    retry.raise_for_status()
    assert first.json()['message_id'] == retry.json()['message_id']
    rows = db.execute('SELECT model FROM app.turns WHERE conversation_id=%s', (conv,)).fetchall()
    assert len(rows) == 1
    assert rows[0]['model'] == model
