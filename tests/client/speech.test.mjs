import test from "node:test";
import assert from "node:assert/strict";
import {
  streamSpeech,
  releaseCloudSpeech,
} from "../../.local-data/client-tests/speechStream.js";
class Socket {
  static OPEN = 1;
  readyState = 1;
  bufferedAmount = 0;
  sent = [];
  constructor() {
    Socket.last = this;
  }
  send(data) {
    this.sent.push(data);
  }
  close() {
    this.readyState = 3;
  }
  message(data) {
    return this.onmessage({ data: JSON.stringify(data) });
  }
}
globalThis.WebSocket = Socket;
const load = async () => ({
  url: "ws://localhost/speech-ws/fixture",
  token: "fixture-ticket",
});
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

test("release before session response never starts recording", async () => {
  let resolveSession,
    captured = false;
  const pending = streamSpeech(
    () => new Promise((resolve) => (resolveSession = resolve)),
    async () => {
      captured = true;
      return async () => {};
    },
  );
  releaseCloudSpeech();
  resolveSession(await load());
  assert.equal(await pending, "");
  assert.equal(captured, false);
});

test("release finalizes once and only authoritative final is returned", async () => {
  let stopped = 0,
    partial = "";
  const pending = streamSpeech(
    load,
    async () => async () => {
      stopped++;
    },
    (text) => (partial = text),
  );
  await tick();
  const ws = Socket.last;
  ws.onopen();
  assert.equal(JSON.parse(ws.sent[0]).token, "fixture-ticket");
  await ws.message({ type: "ready" });
  await ws.message({ type: "partial", text: "草稿" });
  assert.equal(partial, "草稿");
  releaseCloudSpeech();
  await tick();
  assert.deepEqual(JSON.parse(ws.sent[1]), { type: "finish" });
  await ws.message({ type: "partial", text: "松手后重新从头转写" });
  assert.equal(partial, "草稿", "released preview must stay frozen until final submission");
  await ws.message({ type: "final", text: "最终文字" });
  assert.equal(await pending, "最终文字");
  assert.equal(stopped, 1);
  assert.equal(ws.readyState, 3);
});

test("cancel while capture permission is pending aborts without sending", async () => {
  let signal;
  const pending = streamSpeech(load, async (_audio, abort) => {
    signal = abort;
    await new Promise((_, reject) =>
      abort.addEventListener("abort", () => reject(new Error("cancelled"))),
    );
  });
  await tick();
  const ws = Socket.last;
  ws.onopen();
  const ready = ws.message({ type: "ready" });
  releaseCloudSpeech(true);
  assert.equal(await pending, "");
  await ready;
  assert.equal(signal.aborted, true);
  assert.equal(ws.sent.length, 1);
});

test("disconnect after partial must fail rather than sending a draft", async () => {
  const pending = streamSpeech(load, async () => async () => {});
  await tick();
  const ws = Socket.last;
  ws.onopen();
  await ws.message({ type: "ready" });
  await ws.message({ type: "partial", text: "不可发送草稿" });
  ws.onclose();
  await assert.rejects(pending, /SPEECH_INCOMPLETE/);
});

test("audio before network ready survives release and flushes before finish", async () => {
  let emit,
    resolveSession,
    stopped = 0;
  const pending = streamSpeech(
    () => new Promise((resolve) => (resolveSession = resolve)),
    async (audio) => {
      emit = audio;
      return async () => {
        stopped++;
      };
    },
  );
  await tick();
  emit(new Uint8Array([1, 2, 3, 4]).buffer);
  releaseCloudSpeech();
  await tick();
  assert.equal(stopped, 1);
  resolveSession(await load());
  await tick();
  const ws = Socket.last;
  ws.onopen();
  await ws.message({ type: "ready" });
  await tick();
  assert.ok(ws.sent[1] instanceof ArrayBuffer);
  assert.deepEqual(Array.from(new Uint8Array(ws.sent[1])), [1, 2, 3, 4]);
  assert.deepEqual(JSON.parse(ws.sent[2]), { type: "finish" });
  await ws.message({ type: "final", text: "明天下午三点开会" });
  assert.equal(await pending, "明天下午三点开会");
  assert.equal(stopped, 1);
});
