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
  list: (query = "", signal?: AbortSignal) =>
    request<{ items: NoteSummary[]; has_more: boolean }>(
      `/notes?query=${encodeURIComponent(query)}`,
      "GET",
      undefined,
      undefined,
      { signal },
    ),
  get: (id: string) => request<Note>(`/notes/${id}`),
  save: (note: Note) =>
    request<Note>(
      note.revision ? `/notes/${note.id}` : "/notes",
      note.revision ? "PATCH" : "POST",
      note,
    ),
  remove: (note: Note) =>
    request(`/notes/${note.id}?revision=${note.revision}`, "DELETE"),
};
// Drafts survive tab navigation within this session only, never another account.
export const noteDrafts = new Map<string, Note>();
window.addEventListener("adex:session-changed", () => noteDrafts.clear());
