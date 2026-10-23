import { streamSpeech, type SpeechCapture } from "./speechStream";
export { releaseCloudSpeech, type SpeechCapture } from "./speechStream";
export function cloudSpeech(
  capture: SpeechCapture,
  onPartial?: (text: string) => void,
) {
  return streamSpeech(
    async () => {
      const { request } = await import("./api");
      const session = await request<{ session_id: string; token: string }>(
        "/speech/session",
        "POST",
      );
      const base = import.meta.env.VITE_ADEX_API_BASE || location.origin;
      const url = new URL("/speech-ws/" + session.session_id, base);
      url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
      return { url: url.toString(), token: session.token };
    },
    capture,
    onPartial,
  );
}

export const browserCapture: SpeechCapture = async (audio, signal) => {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
  });
  if (signal.aborted) {
    stream.getTracks().forEach((track) => track.stop());
    throw new Error("SPEECH_CANCELLED");
  }
  let context: AudioContext | undefined;
  try {
    context = new AudioContext({ sampleRate: 16000 });
    await context.resume();
    if (context.sampleRate !== 16000) throw new Error("SPEECH_AUDIO_FORMAT");
    const source = context.createMediaStreamSource(stream),
      processor = context.createScriptProcessor(2048, 1, 1);
    source.connect(processor);
    processor.connect(context.destination);
    processor.onaudioprocess = (event) => {
      const input = event.inputBuffer.getChannelData(0),
        pcm = new Int16Array(input.length);
      for (let i = 0; i < input.length; i++)
        pcm[i] = Math.max(-1, Math.min(1, input[i])) * 32767;
      audio(pcm.buffer);
    };
    return async () => {
      processor.onaudioprocess = null;
      processor.disconnect();
      source.disconnect();
      stream.getTracks().forEach((track) => track.stop());
      if (context?.state !== "closed") await context?.close();
    };
  } catch (error) {
    stream.getTracks().forEach((track) => track.stop());
    await context?.close();
    throw error;
  }
};
