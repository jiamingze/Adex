import { createReadResource } from "./readResource";
import { request } from "./api";
export type Note = {
  id: string;
  title: string;
  content: string;
  pinned: boolean;
  revision: number;
  updated_at: string;
};
export type NoteSummary = Omit<Note, "content"> & { preview: string };
export const notesApi = {
  convert: (conversation_id: string, message_id: string) =>
    boundedWrite<Note>(
      (signal) =>
        request<Note>(
          "/notes/from-message",
          "POST",
          { conversation_id, message_id },
          undefined,
          { signal },
        ),
      90000,
    ),
  list: (query = "", signal?: AbortSignal) =>
    request<{ items: NoteSummary[]; has_more: boolean }>(
      `/notes?query=${encodeURIComponent(query)}`,
      "GET",
      undefined,
      undefined,
      { signal },
    ),
  get: (id: string, signal?: AbortSignal) =>
    request<Note>(`/notes/${id}`, "GET", undefined, undefined, { signal }),
  save: (note: Note) =>
    boundedWrite<Note>((signal) =>
      request<Note>(
        note.revision ? `/notes/${note.id}` : "/notes",
        note.revision ? "PATCH" : "POST",
        note,
        undefined,
        { signal },
      ),
    ),
  remove: (note: Note) =>
    boundedWrite((signal) =>
      request(
        `/notes/${note.id}?revision=${note.revision}`,
        "DELETE",
        undefined,
        undefined,
        { signal },
      ),
    ),
};
// A deadline stops the UI waiting, not proof that a server-side write failed.
function boundedWrite<T>(
  run: (signal: AbortSignal) => Promise<T>,
  timeoutMs = 8000,
) {
  const resource = createReadResource(run, { timeoutMs });
  const cancel = () => resource.reset();
  window.addEventListener("adex:session-changed", cancel);
  return resource
    .load()
    .finally(() => window.removeEventListener("adex:session-changed", cancel));
}
export const notesLists = new Map<
  string,
  ReturnType<
    typeof createReadResource<{ items: NoteSummary[]; has_more: boolean }>
  >
>();
export const noteDetails = new Map<
  string,
  ReturnType<typeof createReadResource<Note>>
>();
export const convertedReplies = new Map<string, string>();
export const noteView = { query: "", selected: "" };
export function notesList(query: string) {
  if (!notesLists.has(query)) {
    if (notesLists.size >= 12) {
      const key = notesLists.keys().next().value!;
      notesLists.get(key)?.reset();
      notesLists.delete(key);
    }
    notesLists.set(
      query,
      createReadResource((signal) => notesApi.list(query, signal)),
    );
  }
  return notesLists.get(query)!;
}
export function noteDetail(id: string) {
  if (!noteDetails.has(id)) {
    if (noteDetails.size >= 50) {
      const key = noteDetails.keys().next().value!;
      noteDetails.get(key)?.reset();
      noteDetails.delete(key);
    }
    noteDetails.set(
      id,
      createReadResource((signal) => notesApi.get(id, signal)),
    );
  }
  return noteDetails.get(id)!;
}
export function acceptNote(note: Note) {
  noteDetail(note.id).accept(note);
  notesLists.forEach((resource, query) => {
    const snapshot = resource.getSnapshot().data;
    if (!snapshot) return;
    const rows = snapshot.items.filter((item) => item.id !== note.id);
    if (
      (note.title + "\n" + note.content)
        .toLocaleLowerCase()
        .includes(query.toLocaleLowerCase())
    )
      rows.push({ ...note, preview: note.content.slice(0, 160) });
    rows.sort(
      (a, b) =>
        Number(b.pinned) - Number(a.pinned) ||
        Date.parse(b.updated_at) - Date.parse(a.updated_at),
    );
    resource.accept({
      ...snapshot,
      items: rows.slice(0, 200),
      has_more: snapshot.has_more || rows.length > 200,
    });
  });
}
export function forgetNote(id: string) {
  convertedReplies.forEach((note, message) => {
    if (note === id) convertedReplies.delete(message);
  });
  noteDetails.get(id)?.reset();
  noteDetails.delete(id);
  notesLists.forEach((resource) => {
    const data = resource.getSnapshot().data;
    if (data)
      resource.accept({
        ...data,
        items: data.items.filter((n) => n.id !== id),
      });
  });
}
// Drafts survive tab navigation within this session only, never another account.
export const noteDrafts = new Map<string, Note>();
window.addEventListener("adex:session-changed", () => {
  convertedReplies.clear();
  noteDrafts.clear();
  notesLists.forEach((r) => r.reset());
  notesLists.clear();
  noteDetails.forEach((r) => r.reset());
  noteDetails.clear();
  noteView.query = "";
  noteView.selected = "";
});
window.addEventListener("beforeunload", (event) => {
  if (noteDrafts.size) {
    event.preventDefault();
    event.returnValue = "";
  }
});
