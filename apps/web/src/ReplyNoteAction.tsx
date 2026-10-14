import { useRef, useState } from "react";
import { LoaderCircle, NotebookPen } from "lucide-react";
import { notesApi, acceptNote, convertedReplies } from "./notesApi";

/** Explicit conversion only; success follows an App-committed note response. */
export function ReplyNoteAction({
  conversation,
  message,
  guest,
  onSignIn,
  onOpen,
}: {
  conversation: string;
  message: string;
  guest: boolean;
  onSignIn: () => void;
  onOpen: (id: string) => void;
}) {
  const [pending, setPending] = useState(false),
    [error, setError] = useState(""),
    [saved, setSaved] = useState(convertedReplies.get(message));
  const inFlight = useRef(false);
  async function convert() {
    if (guest) {
      onSignIn();
      return;
    }
    if (inFlight.current) return;
    if (saved) {
      onOpen(saved);
      return;
    }
    inFlight.current = true;
    setPending(true);
    setError("");
    try {
      const note = await notesApi.convert(conversation, message);
      acceptNote(note);
      convertedReplies.set(message, note.id);
      setSaved(note.id);
    } catch {
      setError("整理笔记未完成，请重试；原回复未改变。");
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }
  return (
    <span className="reply-note-action">
      <button
        className="text-button"
        aria-label={pending ? "正在整理笔记" : saved ? "打开笔记" : "转成笔记"}
        title={pending ? "正在整理笔记" : saved ? "打开笔记" : "转成笔记"}
        aria-busy={pending}
        disabled={pending}
        onClick={() => void convert()}
      >
        {pending ? (
          <LoaderCircle size={16} className="note-convert-spinner" />
        ) : (
          <NotebookPen size={16} />
        )}
      </button>
      {error && <small role="status">{error}</small>}
    </span>
  );
}
