/** One gesture owns capture, socket and transcript. No credentials in URLs/storage. */
export type SpeechCapture = (
  audio: (pcm: ArrayBuffer) => void,
  signal: AbortSignal,
) => Promise<() => Promise<void>>;
let current:
  | { release: boolean; stop?: (cancel?: boolean) => void }
  | undefined;
export function releaseCloudSpeech(cancel = false) {
  if (current) {
    current.release = true;
    current.stop?.(cancel);
  }
}
export async function streamSpeech(
  load: () => Promise<{ url: string; token: string }>,
  capture: SpeechCapture,
  onPartial?: (text: string) => void,
) {
  if (current) throw new Error("SPEECH_BUSY");
  const gesture: { release: boolean; stop?: (cancel?: boolean) => void } = {
    release: false,
  };
  current = gesture;
  const captureAbort = new AbortController();
  let socket: WebSocket | undefined,
    stopCapture: (() => Promise<void>) | undefined;
  let captureStopped: Promise<void> | undefined;
  const stopCaptureOnce = () =>
    stopCapture ? (captureStopped ??= stopCapture()) : Promise.resolve();
  let timer: ReturnType<typeof setTimeout> | undefined;
  let captureTimer: ReturnType<typeof setTimeout> | undefined;
  try {
    const session = await load();
    if (gesture.release) return "";
    socket = new WebSocket(session.url);
    const ws = socket;
    return await new Promise<string>((resolve, reject) => {
      let settled = false,
        started = false,
        finishing = false;
      const done = (text?: string, error?: Error) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        error ? reject(error) : resolve(text || "");
      };
      const finish = () => {
        if (settled || finishing || !stopCapture) return;
        finishing = true;
        stopCaptureOnce()
          .then(() => {
            if (ws.readyState === WebSocket.OPEN)
              ws.send(JSON.stringify({ type: "finish" }));
            else done("", new Error("SPEECH_CONNECTION_FAILED"));
          })
          .catch(() => done("", new Error("SPEECH_CAPTURE_FAILED")));
      };
      gesture.stop = (cancel = false) => {
        if (cancel) {
          captureAbort.abort();
          done("");
          return;
        }
        if (!stopCapture) captureAbort.abort();
        if (!started) {
          done("");
          return;
        }
        finish();
      };
      timer = setTimeout(() => done("", new Error("SPEECH_TIMEOUT")), 65000);
      ws.onopen = () => {
        if (gesture.release) {
          done("");
          return;
        }
        ws.send(JSON.stringify({ token: session.token }));
      };
      ws.onerror = () => done("", new Error("SPEECH_CONNECTION_FAILED"));
      ws.onclose = () => {
        if (!settled) done("", new Error("SPEECH_INCOMPLETE"));
      };
      ws.onmessage = async (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "ready" && !started) {
            started = true;
            if (gesture.release) {
              done("");
              return;
            }
            stopCapture = await capture((pcm) => {
              if (!settled && ws.readyState === WebSocket.OPEN) {
                if (ws.bufferedAmount > 128000) {
                  done("", new Error("SPEECH_NETWORK_SLOW"));
                  return;
                }
                ws.send(pcm);
              }
            }, captureAbort.signal);
            if (settled) {
              await stopCaptureOnce();
              return;
            }
            if (gesture.release) finish();
            else captureTimer = setTimeout(finish, 44000);
          } else if (data.type === "partial" && !settled)
            onPartial?.(data.text);
          else if (data.type === "final") done(data.text);
          else if (data.type === "error")
            done("", new Error(data.code || "SPEECH_UNAVAILABLE"));
        } catch {
          gesture.release
            ? done("")
            : done("", new Error("SPEECH_UNAVAILABLE"));
        }
      };
    });
  } finally {
    clearTimeout(timer);
    clearTimeout(captureTimer);
    captureAbort.abort();
    socket?.close();
    await stopCaptureOnce();
    if (current === gesture) current = undefined;
  }
}
