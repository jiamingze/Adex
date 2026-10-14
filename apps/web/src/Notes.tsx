import { useEffect, useState } from "react";
import {
  ArrowLeft,
  Search,
  Plus,
  Pin,
  Trash2,
  NotebookPen,
  Check,
} from "lucide-react";
import { notesApi, noteDrafts, type Note, type NoteSummary } from "./notesApi";
import "./notes.css";
import { createReadResource } from "./readResource";
export function Notes() {
  const [items, setItems] = useState<NoteSummary[]>([]),
    [selected, setSelected] = useState<Note | null>(null);
  const [query, setQuery] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true),
    [more, setMore] = useState(false);
  const [revision, setRevision] = useState(0),
    [saved, setSaved] = useState(false);
  useEffect(() => {
    let live = true;
    setLoading(true);
    const resource = createReadResource((signal) =>
      notesApi.list(query, signal),
    );
    const timer = setTimeout(() => {
      resource
        .load()
        .then((result) => {
          if (live) {
            setItems(result.items);
            setMore(result.has_more);
            setError("");
          }
        })
        .catch(() => {
          if (live) setError("笔记读取失败，请重试。");
        })
        .finally(() => {
          if (live) setLoading(false);
        });
    }, 200);
    return () => {
      live = false;
      clearTimeout(timer);
      resource.reset();
    };
  }, [query, revision]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (noteDrafts.size) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, []);
  const draftRows = Array.from(noteDrafts.values())
    .filter((n) => !n.revision)
    .map((n) => ({ ...n, preview: n.content }));
  async function open(id: string) {
    if (busy) return;
    setError("");
    setBusy(true);
    try {
      setSelected(noteDrafts.get(id) ?? (await notesApi.get(id)));
      setSaved(false);
    } catch {
      setError("无法打开笔记，请重试。");
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
      setSelected(result);
      noteDrafts.delete(result.id);
      setSaved(true);
      setRevision((n) => n + 1);
    } catch (error) {
      setError(
        String(error).includes("REVISION_CONFLICT")
          ? "此笔记已在其他设备更新。草稿仍保留，请复制内容后重新打开原笔记核对。"
          : "保存失败，草稿仍保留，请重试。",
      );
    } finally {
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
      const original = await notesApi.get(selected.id);
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
  async function remove() {
    if (!selected || busy || !window.confirm("删除这条笔记？删除后无法恢复。"))
      return;
    setBusy(true);
    try {
      if (selected.revision) await notesApi.remove(selected);
      noteDrafts.delete(selected.id);
      setSelected(null);
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
          <span className="eyebrow">YOUR NOTES</span>
          <h1>笔记</h1>
          <p>记下想法、会议记录和生活事项。</p>
        </div>
        <button className="notes-primary" onClick={create} disabled={busy}>
          <Plus size={18} />
          新建笔记
        </button>
      </header>
      {error && (
        <div className="experience-inline-error" role="alert">
          {error}
          <button onClick={() => setRevision((n) => n + 1)}>重试</button>
        </div>
      )}
      <div className="notes-layout">
        <aside className="notes-list">
          <label className="notes-search">
            <Search size={17} />
            <input
              aria-label="搜索笔记"
              placeholder="搜索笔记"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          {loading && !items.length && <p>正在读取笔记…</p>}
          {[...draftRows, ...items].map((note) => (
            <button
              className={`note-row ${selected?.id === note.id ? "selected" : ""}`}
              key={note.id}
              onClick={() => open(note.id)}
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
                  onClick={() => setSelected(null)}
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
                <button aria-label="删除笔记" disabled={busy} onClick={remove}>
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
                disabled={busy}
                onChange={(e) => edit({ title: e.target.value })}
              />
              <textarea
                className="note-body"
                aria-label="笔记正文"
                placeholder="从这里开始记录…"
                maxLength={100000}
                value={selected.content}
                disabled={busy}
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
