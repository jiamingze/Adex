"""Bounded stdio RPC; transport failure never implies a turn did not execute."""

import asyncio
import json


class ProtocolFailure(Exception):
    pass


class CodexTransport:
    def __init__(self, command, cwd, env):
        self.command = command
        self.cwd = cwd
        self.env = env
        self.pending = {}
        self.events = asyncio.Queue(maxsize=256)
        self.sequence = 0
        self.failure = None
        self.process = None
        self.reader = None
        self.write_lock = asyncio.Lock()

    async def __aenter__(self):
        self.process = await asyncio.create_subprocess_exec(
            *self.command,
            cwd=self.cwd,
            env=self.env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            limit=1024 * 1024,
        )
        self.reader = asyncio.create_task(self._read())
        return self

    async def __aexit__(self, *_):
        self._fail("CODEX_CLOSED_UNKNOWN")
        if self.reader:
            self.reader.cancel()
            await asyncio.gather(self.reader, return_exceptions=True)
        if self.process and self.process.returncode is None:
            try:
                self.process.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(self.process.wait(), 5)
            except TimeoutError:
                self.process.kill()
                await self.process.wait()

    def _fail(self, code):
        self.failure = self.failure or code
        for future in self.pending.values():
            if not future.done():
                future.set_exception(ProtocolFailure(self.failure))
        # A sentinel wakes next_event even if the subprocess dies while idle.
        if not self.events.full():
            self.events.put_nowait(None)

    async def _read(self):
        try:
            while line := await self.process.stdout.readline():
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError("Invalid RPC frame")
                if "method" in message:
                    self.events.put_nowait(message)
                elif "id" in message and ("result" in message or "error" in message):
                    future = self.pending.get(message["id"])
                    if future and not future.done():
                        future.set_result(message)
                else:
                    raise ValueError("Invalid RPC frame")
            self._fail("CODEX_EOF_UNKNOWN")
        except (ValueError, TypeError, asyncio.QueueFull, OSError):
            self._fail("CODEX_PROTOCOL_UNKNOWN")

    async def send(self, message):
        if self.failure:
            raise ProtocolFailure(self.failure)
        data = (json.dumps(message) + "\n").encode()
        if len(data) > 1024 * 1024:
            raise ProtocolFailure("CODEX_INPUT_LIMIT")
        async with self.write_lock:
            try:
                self.process.stdin.write(data)
                await self.process.stdin.drain()
            except (OSError, ConnectionError):
                self._fail("CODEX_PIPE_UNKNOWN")
                raise ProtocolFailure(self.failure) from None

    async def request(self, method, params, timeout=30):
        if self.failure:
            raise ProtocolFailure(self.failure)
        self.sequence += 1
        request_id = self.sequence
        future = asyncio.get_running_loop().create_future()
        self.pending[request_id] = future
        try:
            async with asyncio.timeout(timeout):
                await self.send({"id": request_id, "method": method, "params": params})
                response = await future
            if "error" in response:
                raise ProtocolFailure("CODEX_RPC_REJECTED")
            return response["result"]
        except TimeoutError:
            raise ProtocolFailure("CODEX_TIMEOUT_UNKNOWN") from None
        finally:
            self.pending.pop(request_id, None)
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                future.exception()

    async def next_event(self):
        if self.failure:
            raise ProtocolFailure(self.failure)
        event = await self.events.get()
        if event is None:
            raise ProtocolFailure(self.failure)
        return event
