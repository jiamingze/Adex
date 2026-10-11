import hashlib
import hmac
import time
from fastapi import HTTPException


def verify_signature(secret, timestamp, body, signature):
    if not secret:
        raise HTTPException(503, "WEBHOOK_NOT_CONFIGURED")
    try:
        if abs(time.time() - int(timestamp)) > 300 or len(body) > 65536:
            raise ValueError()
        expected = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(401, "INVALID_WEBHOOK_SIGNATURE") from None
