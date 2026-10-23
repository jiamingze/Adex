# ruff: noqa: F401,F811
"""Isolated PG/checkpoint/outbox: evidence identity, not LLM wording, controls change-only push."""
import hashlib,json
from uuid import uuid4
from datetime import datetime,timezone,timedelta
from psycopg.types.json import Jsonb
from test_reliability import client,db,write,wait


def test_changes_only_uses_observed_facts_and_still_backfills_every_result(client,db):
    owner=client.get('/api/v1/me').json()['id']
    conv=client.post('/api/v1/conversations',json={'title':'TEST_FIXTURE observation notification'}).json()['id']
    response=client.post('/api/v1/automations',json={
        'origin_conversation_id':conv,'title':'TEST_FIXTURE','instruction':'Check synthetic source',
        'kind':'DAILY','local_time':'08:00','timezone':'Asia/Shanghai',
        'first_fire_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),
        'notification_policy':'CHANGES_ONLY',
    },headers={'Idempotency-Key':str(uuid4())})
    response.raise_for_status();sid=response.json()['id']
    revision=db.execute('SELECT memory_revision FROM app.users WHERE id=%s',(owner,)).fetchone()['memory_revision']
    for fingerprint,content,notify in [('a'*64,'First summary',True),('a'*64,'Reworded summary',False),('b'*64,'Reworded summary',True)]:
        rid,attempt,ref=map(str,(uuid4(),uuid4(),uuid4()))
        db.execute("INSERT INTO automation.runs(id,schedule_id,owner_id,origin_conversation_id,instruction,status,epoch,attempt_id,worker_id,lease_until,request) VALUES(%s,%s,%s,%s,'TEST_FIXTURE','RUNNING',1,%s,'fixture',now()+interval '60 seconds',%s)",(rid,sid,owner,conv,attempt,Jsonb({'notification_policy':'CHANGES_ONLY'})))
        state={'schema_version':1,'phase':'result','content':content,'artifact':{'observation_fingerprint':fingerprint}}
        sha=hashlib.sha256(json.dumps(state,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
        db.execute("INSERT INTO agent.checkpoints(id,run_id,owner_id,epoch,attempt_id,logical_key,memory_revision,schema_version,state,sha256) VALUES(%s,%s,%s,1,%s,'result',%s,1,%s,%s)",(ref,rid,owner,attempt,revision,Jsonb(state),sha))
        run={'id':rid,'owner_id':owner,'epoch':1,'attempt_id':attempt}
        write(run,'checkpoint',{'checkpoint_ref':ref}).raise_for_status()
        write(run,'complete',{'checkpoint_ref':ref}).raise_for_status()
        event=wait(lambda:db.execute('SELECT * FROM automation.outbox WHERE run_id=%s',(rid,)).fetchone())
        assert event['payload']['notify'] is notify
        assert db.execute('SELECT observation_fingerprint FROM automation.runs WHERE id=%s',(rid,)).fetchone()['observation_fingerprint']==fingerprint
        wait(lambda:db.execute('SELECT delivered_at FROM automation.outbox WHERE run_id=%s',(rid,)).fetchone()['delivered_at'])
        assert db.execute('SELECT count(*) n FROM app.messages WHERE conversation_id=%s AND dedupe_key=%s',(conv,'run:'+rid)).fetchone()['n']==1
        assert db.execute('SELECT count(*) n FROM app.notifications WHERE run_id=%s',(rid,)).fetchone()['n']==int(notify)

    # Two live occurrences finish together. The short surfacing lock must prevent
    # both seeing the same prior fingerprint and both emitting a push.
    pending=[]
    for index in range(2):
        rid,attempt,ref=map(str,(uuid4(),uuid4(),uuid4()))
        db.execute("INSERT INTO automation.runs(id,schedule_id,owner_id,origin_conversation_id,instruction,status,epoch,attempt_id,worker_id,lease_until,request) VALUES(%s,%s,%s,%s,'TEST_FIXTURE','RUNNING',1,%s,'fixture',now()+interval '60 seconds',%s)",(rid,sid,owner,conv,attempt,Jsonb({'notification_policy':'CHANGES_ONLY'})))
        state={'schema_version':1,'phase':'result','content':'Concurrent wording '+str(index),'artifact':{'observation_fingerprint':'c'*64}}
        sha=hashlib.sha256(json.dumps(state,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
        db.execute("INSERT INTO agent.checkpoints(id,run_id,owner_id,epoch,attempt_id,logical_key,memory_revision,schema_version,state,sha256) VALUES(%s,%s,%s,1,%s,'result',%s,1,%s,%s)",(ref,rid,owner,attempt,revision,Jsonb(state),sha))
        run={'id':rid,'owner_id':owner,'epoch':1,'attempt_id':attempt}
        write(run,'checkpoint',{'checkpoint_ref':ref}).raise_for_status()
        pending.append((run,ref))
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses=list(executor.map(lambda item:write(item[0],'complete',{'checkpoint_ref':item[1]}),pending))
    for response in responses:response.raise_for_status()
    events=[db.execute('SELECT payload FROM automation.outbox WHERE run_id=%s',(run['id'],)).fetchone()['payload'] for run,ref in pending]
    assert sum(event['notify'] for event in events)==1
