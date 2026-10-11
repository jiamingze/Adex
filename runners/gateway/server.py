"""Internal fixed-policy code runner gateway. No model keys or database credentials."""

import asyncio
import hashlib
import hmac
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from code_runner import check_game

slots = threading.BoundedSemaphore(2)
key = os.environ["ADEX_RUNNER_KEY"].encode()
if len(key) < 32:
    raise RuntimeError("Runner key is too short")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, body):
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        self.reply(
            200 if self.path == "/health/live" else 404, {"service": "code-runner"}
        )

    def do_POST(self):
        self.connection.settimeout(5)
        if self.path != "/internal/check":
            return self.reply(404, {"code": "NOT_FOUND"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 512000:
                return self.reply(413, {"code": "SOURCE_SIZE_LIMIT"})
            raw = self.rfile.read(size)
            stamp = self.headers.get("X-Timestamp", "")
            if len(raw) != size or abs(time.time() - int(stamp)) > 180:
                raise ValueError()
            signature = hmac.new(
                key, stamp.encode() + b"." + raw, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, self.headers.get("X-Signature", "")):
                raise ValueError()
            body = json.loads(raw)
            source = body["source"]
            if not isinstance(source, str) or len(source) > 128000:
                return self.reply(413, {"code": "SOURCE_SIZE_LIMIT"})
        except Exception:
            return self.reply(401, {"code": "UNAUTHENTICATED"})
        if not slots.acquire(blocking=False):
            return self.reply(429, {"code": "RUNNER_BUSY"})
        try:
            result = asyncio.run(check_game(source))
            self.reply(200, result)
        except Exception:
            self.reply(503, {"code": "CODE_RUNNER_FAILED"})
        finally:
            slots.release()


ThreadingHTTPServer(
    (
        os.getenv("ADEX_RUNNER_BIND", "127.0.0.1"),
        int(os.getenv("ADEX_RUNNER_PORT", "8120")),
    ),
    Handler,
).serve_forever()
