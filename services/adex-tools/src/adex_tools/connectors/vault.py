"""AES-GCM credential envelopes with resource-bound AAD and external key IDs."""

import base64
import json
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException


class CredentialVault:
    def __init__(self, key_env="ADEX_CONNECTOR_ENCRYPTION_KEY"):
        try:
            self.key = base64.b64decode(os.environ[key_env], validate=True)
            if len(self.key) != 32:
                raise ValueError()
        except (KeyError, ValueError):
            raise HTTPException(503, "BLOCKED_EXTERNAL") from None

    def seal(self, value: dict, aad: str) -> str:
        nonce = os.urandom(12)
        cipher = AESGCM(self.key).encrypt(nonce, json.dumps(value).encode(), aad.encode())
        return "v1." + base64.urlsafe_b64encode(nonce + cipher).decode()

    def open(self, envelope: str, aad: str) -> dict:
        try:
            if not envelope.startswith("v1."):
                raise ValueError()
            raw = base64.urlsafe_b64decode(envelope[3:])
            return json.loads(AESGCM(self.key).decrypt(raw[:12], raw[12:], aad.encode()))
        except Exception:
            raise HTTPException(503, "CREDENTIAL_UNAVAILABLE") from None
