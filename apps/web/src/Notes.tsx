import { usePageScroll } from "./usePageScroll";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import {
  ArrowLeft,
  Search,
  Plus,
  Pin,
  Trash2,
  NotebookPen,
  Check,
} from "lucide-react";
import {
  notesApi,
  noteDrafts,
  noteView,
  notesList,
  noteDetail,
  acceptNote,
  forgetNote,
  type Note,
  type NoteSummary,
} from "./notesApi";
import "./notes.css";
export function Notes() {
  const [selected, setSelected] = useState<Note | null>(
    () =>
      noteDrafts.get(noteView.selected) ??
      (noteView.selected
        ? noteDetail(noteView.selected).getSnapshot().data
        : null),
  );
  const [query, setQuery] = useState(noteView.query),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [saving, setSaving] = useState(false),
    [revision, setRevision] = useState(0),
    [saved, setSaved] = useState(false);
  const [opening, setOpening] = useState(false);
  const [menu, setMenu] = useState<NoteSummary | null>(null);
  const press = useRef<{
    timer: ReturnType<typeof setTimeout>;
    x: number;
    y: number;
  } | null>(null);
  const suppressClick = useRef(false);
  const openEpoch = useRef(0);
  function cancelPress() {
    if (press.current) clearTimeout(press.current.timer);
    press.current = null;
  }
  useEffect(
    () => () => {
      cancelPress();
      openEpoch.current++;
    },
    [],
  );
  const listScroll = usePageScroll<HTMLElement>("notes-list:" + query);
  const bodyScroll = usePageScroll<HTMLTextAreaElement>(
    "notes-body:" + (selected?.id ?? ""),
  );
  const resource = notesList(query);
  const snapshot = useSyncExternalStore(
    resource.subscribe,
    resource.getSnapshot,
  );
  const items = snapshot.data?.items ?? [],
    more = snapshot.data?.has_more ?? false,
    loading = snapshot.loading;
  useEffect(() => {
    noteView.query = query;
    const timer = setTimeout(
      () => {
        void resource.load(revision > 0).catch(() => {});
      },
      query ? 150 : 0,
    );
    return () => clearTimeout(timer);
  }, [query, revision, resource]);
  useEffect(() => {
    noteView.selected = selected?.id ?? "";
  }, [selected]);
  useEffect(() => {
    if (!selected || noteDrafts.has(selected.id)) return;
    const latest = snapshot.data?.items.find((item) => item.id === selected.id);
    if (!latest || latest.revision === selected.revision) return;
    let live = true;
    void noteDetail(selected.id)
      .load(true)
      .then((note) => {
        if (live && !noteDrafts.has(note.id)) setSelected(note);
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [selected?.id, snapshot.data]);
  const draftRows = Array.from(noteDrafts.values())
    .filter((n) => !n.revision)
    .map((n) => ({ ...n, preview: n.content }));
  async function open(id: string) {
    if (busy) return;
    const epoch = ++openEpoch.current;
    setError("");
    setSaved(false);
    const cached = noteDrafts.get(id) ?? noteDetail(id).getSnapshot().data;
    // Converted notes already have an authoritative response. Opening that copy
    // must not wait for another mobile network round trip or lock the editor.
    if (cached) {
      setSelected(cached);
      setOpening(false);
      return;
    }
    setOpening(true);
    try {
      const note = await noteDetail(id).load();
      if (epoch === openEpoch.current) setSelected(noteDrafts.get(id) ?? note);
    } catch {
      if (epoch === openEpoch.current) setError("无法打开笔记，请重试。");
    } finally {
      if (epoch === openEpoch.current) setOpening(false);
    }
  }
  async function pinRow(row: NoteSummary) {
    if (busy) return;
    setMenu(null);
    setBusy(true);
    setError("");
    try {
      const draft = noteDrafts.get(row.id);
      if (draft && !draft.revision) {
        const next = { ...draft, pinned: !draft.pinned };
        noteDrafts.set(row.id, next);
        if (selected?.id === row.id) setSelected(next);
        setRevision((n) => n + 1);
      } else {
        const current = await noteDetail(row.id).load(true);
        const result = await notesApi.save({
          ...current,
          pinned: !current.pinned,
        });
        acceptNote(result);
        // Pin only the confirmed server copy; preserve unsaved editor text.
        const latestDraft = noteDrafts.get(row.id);
        if (latestDraft) {
          const next = {
            ...latestDraft,
            pinned: result.pinned,
            revision: result.revision,
            updated_at: result.updated_at,
          };
          noteDrafts.set(row.id, next);
          if (selected?.id === row.id) setSelected(next);
        } else if (selected?.id === row.id) setSelected(result);
      }
    } catch {
      setError("置顶更新失败，请刷新后重试。");
    } finally {
      setBusy(false);
    }
  }
  function edit(patch: Partial<Note>) {
    if (!selected) return;
    const next = { ...selected, ...patch };
    setSelected(next);
    noteDrafts.set(next.id, next);
    setSaved(false);
  }
  function create() {
    openEpoch.current++;
    setOpening(false);
    const note = {
      id: crypto.randomUUID(),
      title: "",
      content: "",
      pinned: false,
      revision: 0,
      updated_at: new Date().toISOString(),
    };
    noteDrafts.set(note.id, note);
    setSelected(note);
    setSaved(false);
    setError("");
  }
  async function save() {
    if (!selected || busy) return;
    setBusy(true);
    setSaving(true);
    setError("");
    try {
      const input = {
        ...selected,
        title:
          selected.title.trim() ||
          selected.content.trim().split("\n")[0].slice(0, 200) ||
          "未命名笔记",
      };
      const result = await notesApi.save(input);
      if (
        !input.revision &&
        (result.title !== input.title ||
          result.content !== input.content ||
          result.pinned !== input.pinned)
      ) {
        throw new Error("REVISION_CONFLICT");
      }
      acceptNote(result);
      const draft = noteDrafts.get(result.id);
      // A confirmed response must not erase text typed while it was in flight.
      if (
        draft &&
        (draft.title !== selected.title ||
          draft.content !== selected.content ||
          draft.pinned !== selected.pinned)
      ) {
        const next = {
          ...draft,
          revision: result.revision,
          updated_at: result.updated_at,
        };
        noteDrafts.set(next.id, next);
        setSelected(next);
        setSaved(false);
      } else {
        setSelected(result);
        noteDrafts.delete(result.id);
        setSaved(true);
      }
      setRevision((n) => n + 1);
    } catch (error) {
      setError(
        String(error).includes("REVISION_CONFLICT")
          ? "此笔记已在其他设备更新。草稿仍保留，请复制内容后重新打开原笔记核对。"
          : "保存尚未确认，草稿仍保留。请核对后重试。",
      );
    } finally {
      setSaving(false);
      setBusy(false);
    }
  }
  async function reloadOriginal() {
    if (
      !selected ||
      busy ||
      !window.confirm(
        "重新读取服务器版本会丢弃当前未保存草稿，请先复制需要保留的内容。继续？",
      )
    )
      return;
    setBusy(true);
    try {
      const original = await noteDetail(selected.id).load(true);
      noteDrafts.delete(selected.id);
      setSelected(original);
      setError("");
      setSaved(false);
    } catch {
      setError("读取失败，草稿仍保留。");
    } finally {
      setBusy(false);
    }
  }
  async function remove(target: Note | NoteSummary | null = selected) {
    if (!target || busy || !window.confirm("删除这条笔记？删除后无法恢复。"))
      return;
    setBusy(true);
    try {
      if (target.revision) await notesApi.remove(target);
      forgetNote(target.id);
      noteDrafts.delete(target.id);
      if (selected?.id === target.id) setSelected(null);
      setMenu(null);
      setRevision((n) => n + 1);
      setError("");
    } catch {
      setError("删除失败，可能已在其他设备修改，请刷新核对。");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className={`notes-page ${selected ? "notes-open" : ""}`}>
      <header className="notes-heading">
        <div>
          <p>
            {snapshot.data
              ? `${query ? "匹配" : "共"} ${items.length + draftRows.length} 条笔记`
              : "你的笔记"}
          </p>
        </div>
        <button className="notes-primary" onClick={create} disabled={busy}>
          <Plus size={18} />
          新建笔记
        </button>
      </header>
      {(!!error || !!snapshot.error) && (
        <div className="experience-inline-error" role="alert">
          {error || "笔记更新失败，已缓存内容仍可查看。"}
          <button onClick={() => setRevision((n) => n + 1)}>重试</button>
        </div>
      )}
      {menu && (
        <div className="note-menu-backdrop" onClick={() => setMenu(null)}>
          <div
            className="note-context-menu"
            role="dialog"
            aria-modal="true"
            aria-label="笔记操作"
            onClick={(event) => event.stopPropagation()}
            onKeyDown={(event) => {
              if (event.key === "Escape") setMenu(null);
              if (event.key === "Tab") {
                const buttons = Array.from(
                  event.currentTarget.querySelectorAll<HTMLButtonElement>(
                    "button:not(:disabled)",
                  ),
                );
                const first = buttons[0],
                  last = buttons[buttons.length - 1];
                if (event.shiftKey && document.activeElement === first) {
                  event.preventDefault();
                  last?.focus();
                } else if (!event.shiftKey && document.activeElement === last) {
                  event.preventDefault();
                  first?.focus();
                }
              }
            }}
          >
            <strong>{menu.title || "未命名笔记"}</strong>
            <button autoFocus disabled={busy} onClick={() => void pinRow(menu)}>
              <Pin size={18} />
              {menu.pinned ? "取消置顶" : "置顶笔记"}
            </button>
            <button disabled={busy} onClick={() => void remove(menu)}>
              <Trash2 size={18} />
              删除笔记
            </button>
            <button onClick={() => setMenu(null)}>取消</button>
          </div>
        </div>
      )}
      <div className="notes-layout">
        <aside ref={listScroll} className="notes-list">
          <label className="notes-search">
            <Search size={17} />
            <input
              aria-label="搜索笔记"
              placeholder="搜索笔记"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          {opening && <p role="status">正在打开笔记…</p>}
          {loading && !items.length && <p>正在读取笔记…</p>}
          {[...draftRows, ...items].map((note) => (
            <button
              className={`note-row ${selected?.id === note.id ? "selected" : ""}`}
              key={note.id}
              onClick={() => {
                if (suppressClick.current) {
                  suppressClick.current = false;
                  return;
                }
                void open(note.id);
              }}
              onContextMenu={(event) => {
                event.preventDefault();
                cancelPress();
                setMenu(note);
              }}
              onKeyDown={(event) => {
                if (event.key === "F10" && event.shiftKey) {
                  event.preventDefault();
                  setMenu(note);
                }
              }}
              onPointerDown={(event) => {
                if (!event.isPrimary || event.button !== 0) return;
                cancelPress();
                suppressClick.current = false;
                press.current = {
                  x: event.clientX,
                  y: event.clientY,
                  timer: setTimeout(() => {
                    suppressClick.current = true;
                    setMenu(note);
                    press.current = null;
                  }, 500),
                };
              }}
              onPointerMove={(event) => {
                if (
                  press.current &&
                  Math.hypot(
                    event.clientX - press.current.x,
                    event.clientY - press.current.y,
                  ) > 10
                )
                  cancelPress();
              }}
              onPointerUp={cancelPress}
              onPointerCancel={cancelPress}
              onPointerLeave={cancelPress}
            >
              <strong>
                {note.pinned && <Pin size={13} />} {note.title || "未命名笔记"}
              </strong>
              <span>
                {noteDrafts.has(note.id) ? "未保存草稿 · " : ""}
                {note.preview.slice(0, 90) || "暂无内容"}
              </span>
              <small>
                {new Date(note.updated_at).toLocaleDateString("zh-CN")}
              </small>
            </button>
          ))}
          {!loading && !items.length && !draftRows.length && (
            <div className="notes-empty">
              <NotebookPen size={28} />
              <p>{query ? "没有匹配的笔记" : "让一个想法有地方留下来"}</p>
            </div>
          )}
          {more && <small>仅显示最近 200 条，请搜索缩小范围。</small>}
        </aside>
        <section className="notes-editor">
          {selected ? (
            <>
              <div className="notes-toolbar">
                <button
                  className="notes-back"
                  onClick={() => {
                    openEpoch.current++;
                    setOpening(false);
                    setSelected(null);
                  }}
                >
                  <ArrowLeft size={18} />
                  全部笔记
                </button>
                <span role="status">
                  {busy
                    ? "处理中…"
                    : saved
                      ? "已保存"
                      : noteDrafts.has(selected.id)
                        ? "未保存 · 草稿在本次会话保留"
                        : ""}
                </span>
                <button
                  aria-label={selected.pinned ? "取消置顶" : "置顶笔记"}
                  aria-pressed={selected.pinned}
                  disabled={busy}
                  onClick={() => edit({ pinned: !selected.pinned })}
                >
                  <Pin size={18} />
                </button>
                <button
                  aria-label="删除笔记"
                  disabled={busy}
                  onClick={() => void remove()}
                >
                  <Trash2 size={18} />
                </button>
                <button
                  className="notes-primary"
                  disabled={busy}
                  onClick={save}
                >
                  <Check size={16} />
                  保存
                </button>
              </div>
              {error && (
                <button disabled={busy} onClick={reloadOriginal}>
                  重新读取服务器版本
                </button>
              )}
              <input
                className="note-title"
                aria-label="笔记标题"
                placeholder="标题"
                maxLength={200}
                value={selected.title}
                disabled={busy && !saving}
                onChange={(e) => edit({ title: e.target.value })}
              />
              <textarea
                ref={bodyScroll}
                className="note-body"
                aria-label="笔记正文"
                placeholder="从这里开始记录…"
                maxLength={100000}
                value={selected.content}
                disabled={busy && !saving}
                onChange={(e) => edit({ content: e.target.value })}
              />
            </>
          ) : (
            <div className="notes-empty">
              <NotebookPen size={36} />
              <h2>给想法留个位置</h2>
              <p>选择一条笔记，或记下今天的第一件事。</p>
              <button className="notes-primary" onClick={create}>
                <Plus size={17} />
                写一条笔记
              </button>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
