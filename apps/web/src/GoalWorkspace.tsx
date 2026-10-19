import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import {
  Target,
  Plus,
  Sparkles,
  X,
  Archive,
  Pencil,
  ChevronDown,
  Check,
  RotateCcw,
} from "lucide-react";
import { assistantApi } from "./assistantApi";
import { goalApi, goalsResource, type Goal } from "./assistantWorkspaceApi";
import "./assistantWorkspace.css";

export function GoalWorkspace() {
  const snap = useSyncExternalStore(
    goalsResource.subscribe,
    goalsResource.getSnapshot,
  );
  const [creating, setCreating] = useState(false),
    [title, setTitle] = useState(""),
    [outcome, setOutcome] = useState(""),
    [steps, setSteps] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [history, setHistory] = useState(false),
    [mock, setMock] = useState(false);
  const [editingGoal, setEditingGoal] = useState<Goal | null>(null);
  const id = useRef(crypto.randomUUID());
  useEffect(() => {
    void goalsResource.load(true).catch(() => {});
  }, []);
  const goals = (snap.data?.items ?? []).filter((g) =>
    history ? g.status === "ARCHIVED" : g.status === "ACTIVE",
  );
  async function work(fn: () => Promise<unknown>) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await fn();
      await goalsResource.load(true);
    } catch {
      // A write response may be lost after commit. Refresh, never blindly republish.
      await goalsResource.load(true).catch(() => {});
      setError("操作尚未确认，请先核对列表再重试。当前输入仍保留。");
    } finally {
      setBusy(false);
    }
  }
  const planSteps = steps
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
  function start() {
    setEditingGoal(null);
    id.current = crypto.randomUUID();
    setTitle("");
    setOutcome("");
    setSteps("");
    setCreating(true);
    setMock(false);
    setError("");
  }
  async function archive(g: Goal) {
    await goalApi.update(g, {
      status: g.status === "ARCHIVED" ? "ACTIVE" : "ARCHIVED",
    });
  }
  return (
    <section className="agent-workspace">
      <header className="agent-section-heading">
        <div>
          <h2>目标</h2>
          <p>把想做的事，变成一步步进展。</p>
        </div>
        <button className="agent-primary" onClick={start} disabled={busy}>
          <Plus size={17} />
          新目标
        </button>
      </header>
      <div className="agent-filter-row">
        <button aria-pressed={!history} onClick={() => setHistory(false)}>
          进行中
        </button>
        <button aria-pressed={history} onClick={() => setHistory(true)}>
          已归档
        </button>
        <small>{goals.length} 个目标</small>
      </div>
      {!!(error || snap.error) && (
        <p className="experience-inline-error" role="alert">
          {error || "目标更新失败，缓存仍可查看。"}
          <button onClick={() => void goalsResource.load(true).catch(() => {})}>
            重试
          </button>
        </p>
      )}
      {creating && (
        <form
          className="goal-compose"
          onSubmit={(e) => {
            e.preventDefault();
            void work(async () => {
              if (editingGoal)
                await goalApi.update(editingGoal, { title, outcome });
              else
                await goalApi.create(id.current, {
                  title,
                  outcome,
                  steps: planSteps,
                });
              setCreating(false);
            });
          }}
        >
          <header>
            <strong>{editingGoal ? "调整目标" : "想达成什么？"}</strong>
            <button
              type="button"
              aria-label="关闭目标编辑"
              disabled={busy}
              onClick={() => setCreating(false)}
            >
              <X size={18} />
            </button>
          </header>
          <label>
            目标
            <input
              required
              disabled={busy}
              maxLength={200}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="例如：完成个人网站上线"
            />
          </label>
          <label>
            完成标准
            <textarea
              disabled={busy}
              maxLength={4000}
              value={outcome}
              onChange={(e) => setOutcome(e.target.value)}
              placeholder="怎样才算做好了？"
              rows={2}
            />
          </label>
          {!editingGoal && (
            <label>
              行动步骤 · 每行一项
              <textarea
                disabled={busy}
                maxLength={2400}
                value={steps}
                onChange={(e) => setSteps(e.target.value)}
                rows={4}
                placeholder="明确范围与内容\n完成设计与开发\n验证后上线"
              />
            </label>
          )}
          <p className="agent-caption">
            {editingGoal
              ? "修改目标不会改动已关联待办，行动内容与截止时间可在待办中调整。"
              : "AI 拆解仅生成可编辑计划。确认后创建真实待办，默认重要、不紧急，截止时间为24小时后，可在待办中调整。归档目标会保留这些待办。"}
          </p>
          {mock && (
            <p role="status">TEST_FIXTURE：当前为模拟计划，请核对后再创建。</p>
          )}
          <footer>
            {!editingGoal && (
              <button
                type="button"
                disabled={busy || !title.trim()}
                onClick={() =>
                  void work(async () => {
                    const draft = await goalApi.plan(title, outcome);
                    setTitle(draft.title);
                    setOutcome(draft.outcome);
                    setSteps(draft.steps.join("\n"));
                    setMock(draft.provider === "mock");
                  })
                }
              >
                <Sparkles size={16} />
                {busy ? "正在处理…" : "让 Adex 拆解"}
              </button>
            )}
            <button
              className="agent-primary"
              disabled={busy || !title.trim() || planSteps.length > 12}
            >
              {editingGoal
                ? "保存目标"
                : `创建目标${planSteps.length ? `与 ${planSteps.length} 项待办` : ""}`}
            </button>
          </footer>
        </form>
      )}
      {snap.loading && !snap.data && <p role="status">正在读取目标…</p>}
      {!goals.length && !snap.loading && !creating && (
        <div className="agent-empty">
          <Target size={30} />
          <h3>{history ? "还没有归档目标" : "给重要的事一个方向"}</h3>
          <p>记录目标、拆成待办，进展会随实际完成情况更新。</p>
          {!history && (
            <button onClick={start}>
              创建第一个目标 <Plus size={16} />
            </button>
          )}
        </div>
      )}
      <div className="goal-grid">
        {goals.map((g) => (
          <article className="goal-card" key={g.id}>
            <header>
              <Target size={18} />
              <strong>{g.title}</strong>
              <button
                aria-label="编辑目标"
                disabled={busy}
                onClick={() => {
                  setEditingGoal(g);
                  setTitle(g.title);
                  setOutcome(g.outcome);
                  setSteps("");
                  setCreating(true);
                  setError("");
                }}
              >
                <Pencil size={17} />
              </button>
              <button
                aria-label={g.status === "ARCHIVED" ? "恢复目标" : "归档目标"}
                title={
                  g.status === "ARCHIVED" ? "恢复目标" : "归档目标，保留待办"
                }
                disabled={busy}
                onClick={() => void work(() => archive(g))}
              >
                {g.status === "ARCHIVED" ? (
                  <RotateCcw size={17} />
                ) : (
                  <Archive size={17} />
                )}
              </button>
            </header>
            {g.outcome && <p>{g.outcome}</p>}
            <div className="goal-progress">
              <progress
                max={Math.max(1, g.total)}
                value={g.done}
                aria-label={`${g.title}完成进度`}
              />
              <small>
                {g.done}/{g.total} 已完成
              </small>
            </div>
            <details open>
              <summary>
                行动清单 <ChevronDown size={14} />
              </summary>
              {g.tasks.map((t) => (
                <button
                  className={`goal-step ${t.status === "DONE" ? "is-done" : ""}`}
                  key={t.id}
                  aria-pressed={t.status === "DONE"}
                  disabled={busy}
                  onClick={() =>
                    void work(async () => {
                      await assistantApi.saveTask({
                        ...t,
                        status: t.status === "DONE" ? "TODO" : "DONE",
                      });
                    })
                  }
                >
                  <span className="goal-step-check">
                    {t.status === "DONE" && <Check size={13} />}
                  </span>
                  <span>{t.title}</span>
                </button>
              ))}
              {!g.tasks.length && (
                <p className="agent-caption">
                  还没有关联待办，可在待办页面规划下一步。
                </p>
              )}
            </details>
          </article>
        ))}
      </div>
    </section>
  );
}
