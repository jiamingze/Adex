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
  const gesture = { release: false, stop: (_cancel = false) => {} };
  current = gesture;
  const controller = new AbortController();
  let ws: WebSocket | undefined,
    stopCapture: (() => Promise<void>) | undefined,
    stopping: Promise<void> | undefined;
  let ready = false,
    settled = false,
    captureEnded = false,
    finishSent = false,
    queuedBytes = 0;
  let queue: ArrayBuffer[] = [];
  let timer: ReturnType<typeof setTimeout> | undefined,
    captureTimer: ReturnType<typeof setTimeout> | undefined;
  const stopOnce = () =>
    stopCapture ? (stopping ??= stopCapture()) : Promise.resolve();
  let complete: (text: string) => void = () => {},
    fail: (error: Error) => void = () => {};
  const result = new Promise<string>((resolve, reject) => {
    complete = (text) => {
      if (settled) return;
      settled = true;
      resolve(text);
    };
    fail = (error) => {
      if (settled) return;
      settled = true;
      reject(error);
    };
  });
  const finish = async () => {
    captureEnded = true;
    try {
      await stopOnce();
      if (settled || !ready || finishSent || !stopCapture) return;
      finishSent = true;
      ws!.send(JSON.stringify({ type: "finish" }));
    } catch {
      fail(new Error("SPEECH_CAPTURE_FAILED"));
    }
  };
  gesture.stop = (cancel = false) => {
    if (cancel) {
      controller.abort();
      complete("");
      return;
    }
    // Permission has not completed: lifting must never start the microphone later.
    if (!stopCapture && !queuedBytes) {
      controller.abort();
      complete("");
      return;
    }
    void finish();
  };
  const sendAudio = (pcm: ArrayBuffer) => {
    if (settled || captureEnded) return;
    if (ready) {
      if (
        !ws ||
        ws.readyState !== WebSocket.OPEN ||
        ws.bufferedAmount > 128000
      ) {
        fail(new Error("SPEECH_NETWORK_SLOW"));
        return;
      }
      ws.send(pcm);
    } else {
      queuedBytes += pcm.byteLength;
      if (queuedBytes > 1440000) {
        fail(new Error("SPEECH_AUDIO_LIMIT"));
        return;
      }
      queue.push(pcm.slice(0));
    }
  };
  timer = setTimeout(() => fail(new Error("SPEECH_TIMEOUT")), 65000);
  // Start capture independently of DNS, tunnel and provider setup. Never delay
  // microphone startup until the user's first sentence has already finished.
  void Promise.resolve()
    .then(async () => {
      if (controller.signal.aborted) return;
      stopCapture = await capture(sendAudio, controller.signal);
      if (settled) {
        await stopOnce();
        return;
      }
      if (gesture.release) await finish();
      else
        captureTimer = setTimeout(() => {
          gesture.release = true;
          void finish();
        }, 44000);
    })
    .catch((error) => {
      if (gesture.release) complete("");
      else
        fail(
          error instanceof Error ? error : new Error("SPEECH_CAPTURE_FAILED"),
        );
    });
  void load()
    .then((session) => {
      if (settled) return;
      ws = new WebSocket(session.url);
      ws.onopen = () => {
        if (!settled) ws!.send(JSON.stringify({ token: session.token }));
      };
      ws.onerror = () => fail(new Error("SPEECH_CONNECTION_FAILED"));
      ws.onclose = () => {
        if (!settled) fail(new Error("SPEECH_INCOMPLETE"));
      };
      ws.onmessage = (event) => {
        if (settled) return;
        try {
          const data = JSON.parse(event.data);
          if (data.type === "ready" && !ready) {
            ready = true;
            // Flush in capture order before finish, including release-before-ready.
            for (const pcm of queue) ws!.send(pcm);
            queue = [];
            queuedBytes = 0;
            if (gesture.release) void finish();
          } else if (data.type === "partial" && !gesture.release) onPartial?.(data.text);
          else if (data.type === "final") complete(data.text);
          else if (data.type === "error")
            fail(new Error(data.code || "SPEECH_UNAVAILABLE"));
        } catch {
          fail(new Error("SPEECH_UNAVAILABLE"));
        }
      };
    })
    .catch((error) =>
      fail(
        error instanceof Error ? error : new Error("SPEECH_CONNECTION_FAILED"),
      ),
    );
  try {
    return await result;
  } finally {
    clearTimeout(timer);
    clearTimeout(captureTimer);
    controller.abort();
    queue = [];
    ws?.close();
    try {
      await stopOnce();
    } finally {
      if (current === gesture) current = undefined;
    }
  }
}
