import { useEffect, useState } from "react";
import { Check, Trash2, Plus } from "lucide-react";
import { assistantApi, type MatrixTask } from "./assistantApi";
const quadrants = [
  { name: "立即处理", hint: "重要且紧急", important: true, urgent: true },
  { name: "安排计划", hint: "重要、不紧急", important: true, urgent: false },
  { name: "考虑委派", hint: "紧急、不重要", important: false, urgent: true },
  {
    name: "减少或放弃",
    hint: "不重要、不紧急",
    important: false,
    urgent: false,
  },
];
export function TaskMatrix() {
  const [tasks, setTasks] = useState<MatrixTask[]>([]),
    [error, setError] = useState(""),
    [title, setTitle] = useState(""),
    [important, setImportant] = useState(true),
    [urgent, setUrgent] = useState(false),
    [due, setDue] = useState(""),
    [pending, setPending] = useState(false);
  async function refresh() {
    setTasks((await assistantApi.tasks()).items);
  }
  async function act(work: () => Promise<unknown>) {
    setPending(true);
    try {
      await work();
      await refresh();
      setError("");
    } catch (e) {
      setError(String(e));
    } finally {
      setPending(false);
    }
  }
  useEffect(() => {
    refresh().catch((e) => setError(String(e)));
  }, []);
  return (
    <div className="content-page">
      <div className="page-heading">
        <div>
          <h1>任务四象限</h1>
          <p>按重要性和紧急性整理待办。自动执行仍使用已有任务与运行体系。</p>
        </div>
      </div>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      <form
        className="matrix-create"
        onSubmit={(e) => {
          e.preventDefault();
          act(async () => {
            await assistantApi.saveTask({
              title,
              important,
              urgent,
              status: "TODO",
              due_at: due ? new Date(due).toISOString() : null,
              run_id: null,
              conversation_id: null,
            });
            setTitle("");
            setDue("");
          });
        }}
      >
        <input
          aria-label="任务标题"
          value={title}
          maxLength={200}
          required
          placeholder="添加需要处理的事情"
          onChange={(e) => setTitle(e.target.value)}
        />
        <label>
          <input
            type="checkbox"
            checked={important}
            onChange={(e) => setImportant(e.target.checked)}
          />
          重要
        </label>
        <label>
          <input
            type="checkbox"
            checked={urgent}
            onChange={(e) => setUrgent(e.target.checked)}
          />
          紧急
        </label>
        <input
          aria-label="截止时间"
          type="datetime-local"
          value={due}
          onChange={(e) => setDue(e.target.value)}
        />
        <button className="primary-button" disabled={pending}>
          <Plus size={16} />
          添加
        </button>
      </form>
      <div className="matrix-grid">
        {quadrants.map((q, index) => (
          <section className={`matrix-quadrant quadrant-${index}`} key={q.name}>
            <h2>{q.name}</h2>
            <p className="muted-text">{q.hint}</p>
            {tasks
              .filter(
                (t) => t.important === q.important && t.urgent === q.urgent,
              )
              .map((t) => (
                <article
                  className={`matrix-task ${t.status === "DONE" ? "done" : ""}`}
                  key={t.id}
                >
                  <div>
                    <strong>{t.title}</strong>
                    {t.due_at && (
                      <small>{new Date(t.due_at).toLocaleString()}</small>
                    )}
                  </div>
                  <div className="matrix-task-controls">
                    <button
                      aria-label={t.status === "DONE" ? "恢复待办" : "完成任务"}
                      className="icon-button"
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
                      <Check size={17} />
                    </button>
                    <select
                      aria-label={`移动任务 ${t.title}`}
                      value={index}
                      disabled={pending}
                      onChange={(e) => {
                        const next = quadrants[Number(e.target.value)];
                        act(() =>
                          assistantApi.saveTask({
                            ...t,
                            important: next.important,
                            urgent: next.urgent,
                          }),
                        );
                      }}
                    >
                      {quadrants.map((x, i) => (
                        <option key={x.name} value={i}>
                          {x.name}
                        </option>
                      ))}
                    </select>
                    <button
                      aria-label={`删除任务 ${t.title}`}
                      className="icon-button"
                      disabled={pending}
                      onClick={() => act(() => assistantApi.deleteTask(t.id))}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </article>
              ))}
            {!tasks.some(
              (t) => t.important === q.important && t.urgent === q.urgent,
            ) && <p className="muted-text">暂无任务</p>}
          </section>
        ))}
      </div>
    </div>
  );
}
