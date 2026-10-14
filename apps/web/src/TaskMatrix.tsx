import { TaskPriority } from "./TaskPriority";
import { usePageScroll } from "./usePageScroll";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Check, Plus, Search, X, Circle, Trash2 } from "lucide-react";
import { assistantApi, type MatrixTask } from "./assistantApi";
import "./taskMatrix.css";
import { matrixResource } from "./matrixResource";

const quadrants = [
  { important: true, urgent: true },
  { important: true, urgent: false },
  { important: false, urgent: true },
  { important: false, urgent: false },
];
const quadrantOf = (t: MatrixTask) =>
  quadrants.findIndex(
    (q) => q.important === t.important && q.urgent === t.urgent,
  );
function errorMessage(error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  if (message.includes("READ_TIMEOUT"))
    return "读取任务超时，请重试。已保存的任务不会丢失。";
  if (message.includes("SIGN_IN_REQUIRED"))
    return "登录后即可保存任务，并在手机与网页之间同步。";
  if (message.includes("REVISION") || message.includes("CONFLICT"))
    return "任务已在其他设备更新，请刷新后重试。";
  return "暂时无法保存或读取任务，请检查连接后重试。";
}
function localDate(iso: string | null) {
  if (!iso) return "";
  const date = new Date(iso);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}
function dueLabel(iso: string) {
  const date = new Date(iso);
  const today = new Date();
  const sameDay = date.toDateString() === today.toDateString();
  return `${sameDay ? "今天" : date.toLocaleDateString("zh-CN", { month: "short", day: "numeric" })} ${date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`;
}

export function TaskMatrix() {
  const pageScroll = usePageScroll<HTMLDivElement>("matrix");
  const snapshot = useSyncExternalStore(
    matrixResource.subscribe,
    matrixResource.getSnapshot,
  );
  const tasks = snapshot.data?.items ?? [];
  const [actionError, setError] = useState("");
  const error =
    actionError || (snapshot.error ? errorMessage(snapshot.error) : "");
  const loading = snapshot.data === null && !snapshot.error;
  const [pending, setPending] = useState(false);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("TODO");
  const [editor, setEditor] = useState<{
    task?: MatrixTask;
    quadrant: number;
  } | null>(null);
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");
  const [deleting, setDeleting] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  async function refresh() {
    return matrixResource.load(true);
  }
  async function act(work: () => Promise<unknown>) {
    if (pending) return;
    setPending(true);
    setError("");
    try {
      await work();
      await refresh();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setPending(false);
    }
  }
  useEffect(() => {
    void matrixResource.load().catch(() => {}); // Resource publishes its bounded error state.
  }, []);
  useEffect(() => {
    if (editor) {
      dialog.current?.showModal();
      dialog.current?.querySelector<HTMLInputElement>("input")?.focus();
    } else {
      dialog.current?.close();
      opener.current?.focus();
    }
  }, [editor !== null]);
  function open(quadrant: number, task?: MatrixTask) {
    if (pending) return;
    opener.current = document.activeElement as HTMLElement;
    setError("");
    setDeleting(false);
    setTitle(task?.title ?? "");
    setDue(localDate(task?.due_at ?? null));
    setEditor({ task, quadrant });
  }
  const active = tasks.filter((t) => t.status === "TODO");
  const completed = tasks.length - active.length;
  const visible = tasks
    .filter(
      (t) =>
        (filter === "ALL" || t.status === filter) &&
        t.title.toLocaleLowerCase().includes(query.toLocaleLowerCase()),
    )
    .sort(
      (a, b) =>
        Number(a.status === "DONE") - Number(b.status === "DONE") ||
        Number(b.important) * 2 +
          Number(b.urgent) -
          (Number(a.important) * 2 + Number(a.urgent)) ||
        (a.due_at ? Date.parse(a.due_at) : Infinity) -
          (b.due_at ? Date.parse(b.due_at) : Infinity),
    );
  return (
    <div ref={pageScroll} className="content-page task-matrix-page">
      <header className="matrix-heading">
        <div>
          <p>分清轻重缓急，让每一步都有进展。</p>
        </div>
        <button className="matrix-primary" onClick={() => open(1)}>
          <Plus size={18} />
          添加任务
        </button>
      </header>
      {snapshot.loading && snapshot.data && (
        <p className="matrix-sync-status" role="status">
          正在更新，已有任务可继续查看
        </p>
      )}
      <div className="matrix-overview">
        <span>
          <strong>{snapshot.data ? active.length : "—"}</strong>待办
        </span>
        <span>
          <strong>
            {snapshot.data
              ? active.filter((t) => t.important && t.urgent).length
              : "—"}
          </strong>
          优先处理
        </span>
        <span>
          <strong>{snapshot.data ? completed : "—"}</strong>已完成
        </span>
      </div>
      <div className="matrix-toolbar">
        <label className="matrix-search">
          <Search size={17} />
          <input
            aria-label="搜索任务"
            placeholder="搜索任务"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {query && (
            <button aria-label="清除搜索" onClick={() => setQuery("")}>
              <X size={16} />
            </button>
          )}
        </label>
        <div className="matrix-filters" aria-label="任务状态">
          {[
            ["TODO", "待办"],
            ["DONE", "已完成"],
            ["ALL", "全部"],
          ].map(([value, label]) => (
            <button
              key={value}
              aria-pressed={filter === value}
              onClick={() => setFilter(value)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      {!editor && error && (
        <p role="alert" className="form-error">
          {error}{" "}
          <button
            disabled={snapshot.loading}
            onClick={() => {
              setError("");
              void matrixResource.load(true).catch(() => {});
            }}
          >
            重试
          </button>
        </p>
      )}
      {loading ? (
        <div className="matrix-loading" role="status">
          正在读取待办…
        </div>
      ) : snapshot.data === null ? (
        <div className="matrix-loading">暂时无法读取待办，请重试。</div>
      ) : (
        <section className="flat-tasks" aria-label="事项列表">
          {visible.map((t) => (
            <article
              className={`attention-row ${t.status === "DONE" ? "is-done" : ""}`}
              key={t.id}
            >
              <button
                className="attention-check"
                aria-label={`${t.status === "DONE" ? "恢复" : "完成"}任务 ${t.title}`}
                disabled={pending}
                onClick={() =>
                  act(() =>
                    assistantApi.saveTask({
                      ...t,
                      status: t.status === "DONE" ? "TODO" : "DONE",
                    }),
                  )
                }
              >
                {t.status === "DONE" ? (
                  <Check size={17} />
                ) : (
                  <Circle size={17} />
                )}
              </button>
              <button
                className="attention-title"
                onClick={() => open(quadrantOf(t), t)}
              >
                <strong>{t.title}</strong>
                <small>{t.due_at ? dueLabel(t.due_at) : "未设截止时间"}</small>
              </button>
              <TaskPriority important={t.important} urgent={t.urgent} />
            </article>
          ))}
          {!visible.length && (
            <p className="experience-empty">
              {query ? "没有匹配的事项" : "暂无事项，添加一件今天想完成的事。"}
            </p>
          )}
        </section>
      )}
      <dialog
        ref={dialog}
        className="matrix-dialog"
        aria-labelledby="matrix-editor-title"
        onCancel={(e) => {
          e.preventDefault();
          if (!pending) setEditor(null);
        }}
        onClick={(e) => {
          if (e.target === e.currentTarget && !pending) setEditor(null);
        }}
      >
        {editor && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!title.trim()) return;
              act(async () => {
                const q = quadrants[editor.quadrant];
                await assistantApi.saveTask({
                  ...(editor.task ?? {
                    status: "TODO",
                    run_id: null,
                    conversation_id: null,
                  }),
                  title: title.trim(),
                  due_at: due ? new Date(due).toISOString() : null,
                  important: q.important,
                  urgent: q.urgent,
                });
                setEditor(null);
              });
            }}
          >
            <header>
              <h2 id="matrix-editor-title">
                {editor.task ? "编辑任务" : "添加任务"}
              </h2>
              <button
                type="button"
                aria-label="关闭编辑"
                disabled={pending}
                onClick={() => setEditor(null)}
              >
                <X size={21} />
              </button>
            </header>
            <label className="matrix-field">
              任务名称
              <input
                autoFocus
                required
                maxLength={200}
                placeholder="你想完成什么？"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </label>
            <fieldset disabled={pending}>
              <legend>重要性与紧急程度</legend>
              <div className="matrix-priority-controls">
                <label>
                  <input
                    type="checkbox"
                    checked={quadrants[editor.quadrant].important}
                    onChange={(e) =>
                      setEditor({
                        ...editor,
                        quadrant: quadrants.findIndex(
                          (q) =>
                            q.important === e.target.checked &&
                            q.urgent === quadrants[editor.quadrant].urgent,
                        ),
                      })
                    }
                  />
                  重要事项
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={quadrants[editor.quadrant].urgent}
                    onChange={(e) =>
                      setEditor({
                        ...editor,
                        quadrant: quadrants.findIndex(
                          (q) =>
                            q.urgent === e.target.checked &&
                            q.important ===
                              quadrants[editor.quadrant].important,
                        ),
                      })
                    }
                  />
                  需要尽快处理
                </label>
              </div>
            </fieldset>
            <label className="matrix-field">
              截止时间 <span>可选</span>
              <input
                type="datetime-local"
                value={due}
                onChange={(e) => setDue(e.target.value)}
              />
            </label>
            {error && (
              <p role="alert" className="form-error">
                {error}
              </p>
            )}
            {deleting && (
              <div className="matrix-delete-confirm">
                <p>确定删除「{editor.task?.title}」？此操作无法撤销。</p>
                <button
                  type="button"
                  disabled={pending}
                  onClick={() =>
                    act(async () => {
                      await assistantApi.deleteTask(editor.task!.id);
                      setEditor(null);
                    })
                  }
                >
                  确认删除
                </button>
                <button
                  type="button"
                  disabled={pending}
                  onClick={() => setDeleting(false)}
                >
                  取消
                </button>
              </div>
            )}
            <footer>
              {editor.task && (
                <button
                  type="button"
                  className="matrix-delete"
                  disabled={pending}
                  onClick={() => setDeleting(true)}
                >
                  <Trash2 size={16} />
                  删除
                </button>
              )}
              <button
                type="submit"
                className="matrix-primary"
                disabled={pending || !title.trim()}
              >
                {pending ? "正在保存…" : "保存任务"}
              </button>
            </footer>
          </form>
        )}
      </dialog>
    </div>
  );
}
