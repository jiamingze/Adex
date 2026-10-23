"""Explicit isolated-test adapter; not proof of macOS or third-party execution."""


def execute(body):
    if body.get("action") and body.get("tree_hash") != "TEST_FIXTURE":
        from fastapi import HTTPException

        raise HTTPException(409, "COMPUTER_STALE_OBSERVATION")
    if body.get("command") == "status":
        return {"accessibility": True}
    return {
        "bundle_id": body.get("bundle_id", "io.adex.fixture"),
        "pid": 123,
        "tree_hash": "TEST_FIXTURE",
        "nodes": [{"id": "0.0", "role": "AXButton", "title": "测试按钮", "actions": ["AXPress"]}],
        "receipt": "TEST_FIXTURE_APPLIED" if body.get("action") else "OBSERVED",
    }
