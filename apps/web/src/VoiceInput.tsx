import { useEffect, useRef, useState, type RefObject } from "react";
import { createPortal } from "react-dom";
import { Mic, LoaderCircle, X } from "lucide-react";
import { transcribe, stopSpeech } from "./platform";

type Phase = "idle" | "recording" | "processing";
export function VoiceInput({
  onText,
  surfaceRef,
  hasText = false,
}: {
  onText: (text: string) => void;
  surfaceRef?: RefObject<HTMLTextAreaElement | null>;
  hasText?: boolean;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [hint, setHint] = useState("");
  const [cancel, setCancel] = useState(false);
  const cancelled = useRef(false),
    startY = useRef(0);
  const buttonTimer = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined,
  );
  const active = useRef(false),
    held = useRef(false),
    mounted = useRef(true);
  useEffect(() => {
    if (phase === "idle") return;
    // The sheet lets pointer events reach the held control. Suppress selection
    // on the underlying page only for this capture, and restore it on teardown.
    const clearSelection = () => {
      const selection = window.getSelection();
      if (selection?.rangeCount) selection.removeAllRanges();
    };
    const preventSelection = (event: Event) => event.preventDefault();
    document.documentElement.classList.add("voice-capture-active");
    clearSelection();
    document.addEventListener("selectstart", preventSelection, true);
    document.addEventListener("contextmenu", preventSelection, true);
    document.addEventListener("selectionchange", clearSelection);
    return () => {
      document.documentElement.classList.remove("voice-capture-active");
      document.removeEventListener("selectstart", preventSelection, true);
      document.removeEventListener("contextmenu", preventSelection, true);
      document.removeEventListener("selectionchange", clearSelection);
    };
  }, [phase]);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      clearTimeout(buttonTimer.current);
      if (active.current) void stopSpeech();
    };
  }, []);
  useEffect(() => {
    if (!hint) return;
    const timer = setTimeout(() => setHint(""), 4000);
    return () => clearTimeout(timer);
  }, [hint]);
  useEffect(() => {
    const surface = surfaceRef?.current;
    if (!surface || hasText) return;
    let timer: ReturnType<typeof setTimeout> | undefined,
      pressed = false,
      moved = false,
      originX = 0,
      originY = 0;
    const clear = () => {
      if (timer) clearTimeout(timer);
      timer = undefined;
    };
    const down = (event: PointerEvent) => {
      if (event.button !== 0 || active.current) return;
      event.preventDefault();
      pressed = true;
      moved = false;
      originX = event.clientX;
      originY = event.clientY;
      startY.current = event.clientY;
      surface.setPointerCapture(event.pointerId);
      timer = setTimeout(() => {
        timer = undefined;
        if (pressed && !moved) void begin();
      }, 350);
    };
    const move = (event: PointerEvent) => {
      if (!pressed) return;
      if (held.current) {
        cancelled.current = originY - event.clientY > 64;
        setCancel(cancelled.current);
      } else if (
        Math.hypot(event.clientX - originX, event.clientY - originY) > 12
      ) {
        moved = true;
        clear();
      }
    };
    const up = () => {
      if (!pressed) return;
      pressed = false;
      clear();
      if (held.current) void release();
      else if (!moved && !active.current) surface.focus();
    };
    const abort = () => {
      pressed = false;
      clear();
      cancelled.current = true;
      void release();
    };
    const hidden = () => {
      if (document.hidden) abort();
    };
    window.addEventListener("pagehide", abort);
    document.addEventListener("visibilitychange", hidden);
    const menu = (event: Event) => event.preventDefault();
    surface.addEventListener("pointerdown", down);
    surface.addEventListener("pointermove", move);
    surface.addEventListener("pointerup", up);
    surface.addEventListener("pointercancel", abort);
    surface.addEventListener("contextmenu", menu);
    return () => {
      clear();
      surface.removeEventListener("pointerdown", down);
      surface.removeEventListener("pointermove", move);
      surface.removeEventListener("pointerup", up);
      surface.removeEventListener("pointercancel", abort);
      surface.removeEventListener("contextmenu", menu);
      window.removeEventListener("pagehide", abort);
      document.removeEventListener("visibilitychange", hidden);
    };
  }, [surfaceRef, hasText]);
  useEffect(() => {
    const end = () => {
      clearTimeout(buttonTimer.current);
      void release();
    };
    const cancelRecording = () => {
      cancelled.current = true;
      end();
    };
    const visibility = () => {
      if (document.hidden) cancelRecording();
    };
    window.addEventListener("pointerup", end);
    window.addEventListener("pointercancel", cancelRecording);
    window.addEventListener("pagehide", cancelRecording);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      window.removeEventListener("pointerup", end);
      window.removeEventListener("pointercancel", cancelRecording);
      window.removeEventListener("pagehide", cancelRecording);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, []);
  async function begin() {
    if (active.current) return;
    active.current = true;
    held.current = true;
    cancelled.current = false;
    setCancel(false);
    setHint("");
    setPhase("recording");
    if (
      document.activeElement instanceof HTMLInputElement ||
      document.activeElement instanceof HTMLTextAreaElement
    )
      document.activeElement.blur();
    try {
      const text = (await transcribe()).trim();
      if (mounted.current) {
        if (cancelled.current) setHint("已取消录音");
        else if (text) onText(text);
        else setHint("没有听清，请长按重试");
      }
    } catch (error) {
      if (mounted.current) {
        const message = String(error);
        setHint(
          cancelled.current
            ? "已取消录音"
            : message.includes("PERMISSION")
              ? "请在系统设置中允许麦克风和语音识别"
              : message.includes("UNAVAILABLE")
                ? "语音识别暂不可用，请稍后重试"
                : message.includes("SPEECH_BUSY")
                  ? "语音正在处理中，请稍后重试"
                  : message.includes("SPEECH_")
                    ? "未能识别语音，请检查麦克风后长按重试"
                    : message.replace(/^Error: /, ""),
        );
      }
    } finally {
      active.current = false;
      held.current = false;
      if (mounted.current) setPhase("idle");
    }
  }
  async function release() {
    if (!held.current) return;
    held.current = false;
    setPhase("processing");
    try {
      await stopSpeech();
    } catch {
      if (mounted.current) setHint("停止录音失败，请重试");
    }
  }
  return (
    <div className="voice-control">
      {(!hasText || phase !== "idle") && (
        <button
          type="button"
          className={`voice-button ${phase} ${cancel ? "cancelling" : ""}`}
          aria-label={
            phase === "recording"
              ? "正在录音，松开转为文字"
              : phase === "processing"
                ? "录音已结束，正在转文字"
                : "长按语音输入"
          }
          aria-describedby={hint ? "voice-hint" : undefined}
          disabled={phase === "processing"}
          onPointerDown={(event) => {
            if (event.button !== 0) return;
            event.preventDefault();
            startY.current = event.clientY;
            event.currentTarget.setPointerCapture(event.pointerId);
            clearTimeout(buttonTimer.current);
            buttonTimer.current = setTimeout(() => {
              buttonTimer.current = undefined;
              void begin();
            }, 350);
          }}
          onPointerMove={(event) => {
            if (held.current) {
              cancelled.current = startY.current - event.clientY > 64;
              setCancel(cancelled.current);
            }
          }}
          onPointerUp={() => {
            clearTimeout(buttonTimer.current);
            void release();
          }}
          onPointerCancel={() => {
            clearTimeout(buttonTimer.current);
            cancelled.current = true;
            void release();
          }}
          onLostPointerCapture={() => {
            clearTimeout(buttonTimer.current);
            void release();
          }}
          onContextMenu={(event) => event.preventDefault()}
          onKeyDown={(event) => {
            if ((event.key === " " || event.key === "Enter") && !event.repeat) {
              event.preventDefault();
              clearTimeout(buttonTimer.current);
              buttonTimer.current = setTimeout(() => {
                buttonTimer.current = undefined;
                void begin();
              }, 350);
            }
          }}
          onKeyUp={(event) => {
            if (event.key === " " || event.key === "Enter") {
              event.preventDefault();
              clearTimeout(buttonTimer.current);
              void release();
            }
          }}
          onBlur={() => {
            clearTimeout(buttonTimer.current);
            void release();
          }}
        >
          {phase === "processing" ? (
            <LoaderCircle size={18} className="voice-spinner" />
          ) : (
            <Mic size={24} />
          )}
        </button>
      )}
      {phase !== "idle" &&
        createPortal(
          <>
            <div className="voice-recording-backdrop" aria-hidden="true" />
            <div
              className={`voice-status voice-bottom-sheet ${cancel ? "cancelling" : ""}`}
              role="status"
              aria-live="polite"
            >
              {phase === "recording" ? (
                <>
                  <div className="voice-wave" aria-hidden="true">
                    {Array.from({ length: 13 }, (_, i) => (
                      <i key={i} style={{ animationDelay: `${i * 0.07}s` }} />
                    ))}
                  </div>
                  <strong>{cancel ? "松开取消" : "正在聆听"}</strong>
                  <span>
                    {cancel ? "移回按钮继续录音" : "松开输入 · 上滑取消"}
                  </span>
                </>
              ) : (
                <>
                  <LoaderCircle size={22} className="voice-spinner" />
                  <strong>录音已结束</strong>
                  <span>正在转成文字…</span>
                </>
              )}
            </div>
          </>,
          document.body,
        )}
      {hint && (
        <div id="voice-hint" className="voice-hint" role="status">
          <span>{hint}</span>
          <button
            type="button"
            aria-label="关闭语音提示"
            onClick={() => setHint("")}
          >
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
