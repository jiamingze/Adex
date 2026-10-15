"""Explicit memory commands against isolated PG; no personal data or paid model calls."""
import json
from uuid import uuid4
import httpx
from test_reliability import BASE, client, db, sign, wait


def command(c, database, conv, text, key=None):
    payload = {"content": text, "client_message_id": key or str(uuid4())}
    result = c.post(f"/api/v1/conversations/{conv}/messages", json=payload)
    result.raise_for_status()
    turn = result.json()["message_id"]
    wait(lambda: database.execute("SELECT status FROM app.turns WHERE id=%s", (turn,)).fetchone()["status"] == "COMPLETED")
    reply = database.execute("SELECT content FROM app.messages WHERE dedupe_key=%s", ("turn:"+turn,)).fetchone()["content"]
    return turn, reply


def test_chat_memory_save_correct_forget_and_cross_conversation(client, db):
    conv = client.post("/api/v1/conversations", json={"title":"TEST_FIXTURE memory commands"}).json()["id"]
    owner = client.get("/api/v1/me").json()["id"]
    marker = "TEST_FIXTURE_"+str(uuid4())
    old, new = marker+"我住在上海", marker+"我住在杭州"
    key = str(uuid4())
    turn, reply = command(client,db,conv,"请记住："+old,key)
    assert reply.startswith("已记住：")
    command(client,db,conv,"请记住："+old,key)
    assert db.execute("SELECT count(*) AS n FROM app.memories WHERE owner_id=%s AND content=%s AND deleted_at IS NULL",(owner,old)).fetchone()["n"] == 1
    assert db.execute("SELECT source_refs FROM app.memories WHERE owner_id=%s AND content=%s",(owner,old)).fetchone()["source_refs"] == [turn]
    _, reply = command(client,db,conv,f"把记忆“{old}”更新为“{new}”")
    assert reply.startswith("已更新记忆：")
    other = client.post("/api/v1/conversations", json={"title":"TEST_FIXTURE cross conversation"}).json()["id"]
    context = httpx.get(BASE+"/internal/context/"+other,headers=sign("agent","app","context:read",owner,other),trust_env=False).json()
    assert any(m["content"] == new for m in context["memories"])
    assert old not in json.dumps(context,ensure_ascii=False)
    _, reply = command(client,db,other,"忘记关于"+marker+"的记忆")
    assert reply.startswith("已忘记")
    _, reply = command(client,db,other,"记住："+new)
    assert "没有重新保存" in reply
    assert db.execute("SELECT count(*) AS n FROM app.memories WHERE owner_id=%s AND content IN (%s,%s) AND deleted_at IS NULL",(owner,old,new)).fetchone()["n"] == 0
    # Delayed extraction cannot resurrect the old explicitly corrected fact.
    db.execute("UPDATE app.outbox SET delivered_at=NULL,next_attempt_at=now() WHERE kind='memory.extract' AND resource_id=%s",(turn,))
    wait(lambda: db.execute("SELECT count(*) AS n FROM app.outbox WHERE kind='memory.extract' AND resource_id=%s AND delivered_at IS NULL",(turn,)).fetchone()["n"] == 0)
    assert db.execute("SELECT count(*) AS n FROM app.memories WHERE owner_id=%s AND content=%s AND deleted_at IS NULL",(owner,old)).fetchone()["n"] == 0


def test_ambiguous_disabled_secret_and_guest_memory_commands(client, db):
    conv = client.post("/api/v1/conversations", json={"title":"TEST_FIXTURE memory guardrails"}).json()["id"]
    owner = client.get("/api/v1/me").json()["id"]
    marker = "TEST_FIXTURE_"+str(uuid4())
    ids=[]
    for ending in ["甲","乙"]:
        ids.append(client.post("/api/v1/memories",json={"content":marker+ending}).json()["id"])
    _,reply = command(client,db,conv,"忘记关于"+marker+"的记忆")
    assert "2条" in reply and "未修改" in reply
    _,reply = command(client,db,conv,"请记住：我的密码是TEST_FIXTURE")
    assert "本次未保存" in reply
    original=db.execute("SELECT settings FROM app.users WHERE id=%s",(owner,)).fetchone()["settings"]
    try:
        db.execute("UPDATE app.users SET settings=jsonb_set(settings,'{memory_enabled}','false') WHERE id=%s",(owner,))
        _,reply=command(client,db,conv,"记住："+marker+"丙")
        assert "关闭记忆" in reply
    finally:
        db.execute("UPDATE app.users SET settings=%s::jsonb WHERE id=%s",(json.dumps(original),owner))
        for ident in ids: client.delete("/api/v1/memories/"+ident).raise_for_status()
    with httpx.Client(base_url=BASE,timeout=20,trust_env=False) as guest:
        auth=guest.post("/api/v1/auth/guest",json={});auth.raise_for_status()
        guest.headers.update({"Authorization":"Bearer "+auth.json()["token"]})
        conv=guest.post("/api/v1/conversations",json={"title":"guest memory fixture"}).json()["id"]
        _,reply=command(guest,db,conv,"记住："+marker)
        assert "登录后" in reply


def test_clear_memory_is_owner_scoped_and_list_reflects_commit(client, db):
    sentinel = "TEST_FIXTURE_isolation_" + str(uuid4())
    owned = client.post("/api/v1/memories", json={"content": sentinel})
    owned.raise_for_status()
    try:
        with httpx.Client(base_url=BASE, timeout=20, trust_env=False) as other:
            auth = other.post("/api/v1/auth/register", json={"username":"memory-"+str(uuid4())[:8],"password":"fixture"})
            auth.raise_for_status()
            other.headers.update({"Authorization":"Bearer "+auth.json()["token"]})
            conv = other.post("/api/v1/conversations", json={"title":"TEST_FIXTURE private memory"}).json()["id"]
            command(other, db, conv, "记住：TEST_FIXTURE_只属于另一用户")
            _,reply = command(other, db, conv, "你记住了什么")
            assert "只属于另一用户" in reply and sentinel not in reply
            _,reply = command(other, db, conv, "清空所有记忆")
            assert "1条" in reply
            assert other.get("/api/v1/memories").json()["items"] == []
            assert any(m["content"] == sentinel for m in client.get("/api/v1/memories").json()["items"])
    finally:
        client.delete("/api/v1/memories/" + owned.json()["id"]).raise_for_status()
