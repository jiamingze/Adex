import { useEffect, useState, useSyncExternalStore } from "react";
import {
  ArrowRight,
  RefreshCw,
  Check,
  Sun,
  CalendarDays,
  Sparkles,
  Circle,
  ShieldCheck,
  FolderOpen,
  Clock3,
  Brain,
} from "lucide-react";
import {
  api,
  workspaceApi,
  type Schedule,
  type Run,
  type Artifact,
} from "./api";
import {
  assistantApi,
  type MatrixTask,
  type Action,
  type Signal,
} from "./assistantApi";
import {
  focusTasks,
  dueCaption,
  isDueToday,
  awaitingAction,
  planningPrompt,
} from "./todayModel";
import { calendarResource } from "./calendarResource";
import { upcomingAgenda, agendaTime } from "./calendarAgenda";
import { matrixResource } from "./matrixResource";
import type { AssistantTab } from "./AssistantHub";
import type { Page } from "./navigation";

type Props = {
  guest: boolean;
  username: string;
  onNavigate: (page: Page) => void;
  onConversation: (id: string) => void;
  onPrompt: (text: string) => void;
  onSignIn: () => void;
  onAssistant: (tab: AssistantTab) => void;
};
type Data = {
  tasks: MatrixTask[] | null;
  schedules: Schedule[] | null;
  runs: Run[] | null;
  actions: Action[] | null;
  signals: Signal[] | null;
  artifacts: Artifact[] | null;
  connections: { items: { status: string }[]; availability: string } | null;
};
const empty: Data = {
  tasks: null,
  schedules: null,
  runs: null,
  actions: null,
  signals: null,
  artifacts: null,
  connections: null,
};
const runLabels: Record<string, string> = {
  QUEUED: "等待执行",
  RUNNING: "正在处理",
  COMPLETED: "已完成",
  FAILED: "执行失败",
  UNKNOWN: "结果待核对",
  CANCELLED: "已取消",
};

export function Today({
  guest,
  username,
  onNavigate,
  onConversation,
  onPrompt,
  onSignIn,
  onAssistant,
}: Props) {
  const calendar = useSyncExternalStore(
    calendarResource.subscribe,
    calendarResource.getSnapshot,
  );
  const agenda = upcomingAgenda(calendar.data?.events ?? []);
  const [data, setData] = useState<Data>(empty);
  const [errors, setErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(!guest);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    if (guest) return;
    void calendarResource.load(revision > 0).catch(() => {});
  }, [guest, revision]);
  const [updated, setUpdated] = useState<Date | null>(null);
  const [pending, setPending] = useState("");
  const [taskError, setTaskError] = useState("");
  useEffect(() => {
    if (guest) {
      setData(empty);
      setLoading(false);
      return;
    }
    let live = true;
    setLoading(true);
    // Read projections independently: an unavailable connector must not hide durable tasks.
    Promise.allSettled([
      matrixResource.load(),
      api.schedules(),
      api.runs(),
      assistantApi.actions(),
      assistantApi.signals(),
      workspaceApi.artifacts(),
      assistantApi.connections(),
    ]).then((results) => {
      if (!live) return;
      const next: Data = { ...empty };
      const keys = [
        "tasks",
        "schedules",
        "runs",
        "actions",
        "signals",
        "artifacts",
        "connections",
      ] as const;
      const failures: string[] = [];
      results.forEach((result, i) => {
        if (result.status === "fulfilled") {
          const value = i === 6 ? result.value : result.value.items;
          Object.assign(next, { [keys[i]]: value });
        } else failures.push(keys[i]);
      });
      setData(next);
      setErrors(failures);
      setUpdated(new Date());
      setLoading(false);
    });
    return () => {
      live = false;
    };
  }, [guest, revision]);
  useEffect(() => {
    if (guest) return;
    const refresh = () => {
      if (document.visibilityState === "visible") setRevision((n) => n + 1);
    };
    const timer = window.setInterval(refresh, 30000);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [guest]);
  const now = new Date();
  const focus = focusTasks(data.tasks ?? []);
  const activeRuns =
    data.runs?.filter((r) =>
      ["RUNNING", "QUEUED", "UNKNOWN"].includes(r.status),
    ) ?? [];
  const upcoming =
    data.schedules
      ?.filter((s) => s.status === "ACTIVE" && s.next_fire_at)
      .sort((a, b) => Date.parse(a.next_fire_at!) - Date.parse(b.next_fire_at!))
      .slice(0, 3) ?? [];
  const attention = awaitingAction(data.actions ?? []);
  const date = now.toLocaleDateString("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "long",
  });
  const greeting =
    now.getHours() < 12 ? "早上好" : now.getHours() < 18 ? "下午好" : "晚上好";
  function sectionState(key: string, text: string) {
    return errors.includes(key) ? (
      <p className="experience-inline-error" role="status">
        暂时无法读取，请刷新重试。
      </p>
    ) : loading && !updated ? (
      <p className="experience-empty">正在整理…</p>
    ) : (
      <p className="experience-empty">{text}</p>
    );
  }
  async function complete(task: MatrixTask) {
    if (pending) return;
    setPending(task.id);
    setTaskError("");
    try {
      const saved = await assistantApi.saveTask({ ...task, status: "DONE" });
      setData((d) => ({
        ...d,
        tasks: d.tasks?.map((t) => (t.id === saved.id ? saved : t)) ?? null,
      }));
    } catch {
      setTaskError("未能更新任务，可能已在其他设备修改。请刷新后重试。");
    } finally {
      setPending("");
    }
  }
  return (
    <div className="content-page today-page">
      <header className="today-heading">
        <div>
          <span className="experience-eyebrow">
            <Sun size={14} />
            {date}
          </span>
          <h1>今天</h1>
          <p>
            {greeting}
            {guest ? "，欢迎来到 Adex" : `，${username}`}。
          </p>
        </div>
        <button
          className="experience-icon"
          aria-label="刷新今日概览"
          disabled={loading || guest}
          onClick={() => setRevision((n) => n + 1)}
        >
          <RefreshCw
            size={18}
            className={loading ? "experience-spinning" : ""}
          />
        </button>
      </header>
      <section className="today-invitation">
        <div>
          <span className="today-orb">
            <Sparkles size={24} />
          </span>
          <div>
            <h2>{guest ? "有件事想交给助手？" : "一起梳理今天的重点"}</h2>
            <p>{guest ? "从一句话开始。" : "依据已有待办，整理行动顺序。"}</p>
          </div>
        </div>
        <button
          onClick={() =>
            onPrompt(
              guest
                ? ""
                : planningPrompt(
                    { tasks: data.tasks, schedules: data.schedules },
                    updated ?? now,
                  ),
            )
          }
          className="experience-primary"
        >
          {guest ? "和 Adex 聊聊" : "一起安排今天"}
          <ArrowRight size={16} />
        </button>
      </section>
      {guest ? (
        <>
          <section className="today-onboarding">
            <h2>一个入口，照顾你的日常</h2>
            <div className="today-start-grid">
              {[
                {
                  icon: CalendarDays,
                  title: "安排与跟进",
                  text: "管理待办、提醒和后台任务。",
                  page: "matrix",
                },
                {
                  icon: Brain,
                  title: "记住你的偏好",
                  text: "查看和纠正记忆，让帮助更贴合你。",
                  page: "memory",
                },
                {
                  icon: ShieldCheck,
                  title: "重要操作，由你确认",
                  text: "连接日历与邮件，查看需要处理的变化。",
                  page: "assistant",
                },
              ].map((item) => (
                <button
                  key={item.page}
                  onClick={() => onNavigate(item.page as Page)}
                >
                  <item.icon size={22} />
                  <strong>{item.title}</strong>
                  <span>{item.text}</span>
                  <ArrowRight size={16} />
                </button>
              ))}
            </div>
            <div className="today-signin">
              <div>
                <strong>让手机与网页保持同步</strong>
                <p>登录后，任务、作品和个人记忆都保存在你的账户中。</p>
              </div>
              <button className="experience-primary" onClick={onSignIn}>
                登录或注册
              </button>
            </div>
          </section>
        </>
      ) : (
        <>
          <div className="today-summary">
            <button onClick={() => onNavigate("matrix")}>
              <span>今日到期</span>
              <strong>
                {data.tasks
                  ? focus.filter((t) => isDueToday(t.due_at, now)).length
                  : "—"}
              </strong>
            </button>
            <button onClick={() => onAssistant("actions")}>
              <span>需要你决定</span>
              <strong>{data.actions ? attention.length : "—"}</strong>
            </button>
            <button onClick={() => onNavigate("tasks")}>
              <span>后台处理中</span>
              <strong>
                {data.runs
                  ? activeRuns.filter((r) => r.status !== "UNKNOWN").length
                  : "—"}
              </strong>
            </button>
          </div>
          <div className="today-grid">
            <section className="experience-card">
              <header>
                <h2>
                  <Circle size={17} />
                  优先关注
                </h2>
                <button onClick={() => onNavigate("matrix")}>
                  四象限
                  <ArrowRight size={14} />
                </button>
              </header>
              {taskError && (
                <p className="experience-inline-error" role="alert">
                  {taskError}
                </p>
              )}
              {focus.slice(0, 5).map((t) => (
                <div className="today-task" key={t.id}>
                  <button
                    aria-label={`完成任务 ${t.title}`}
                    disabled={!!pending}
                    onClick={() => complete(t)}
                    className="today-check"
                  >
                    <Circle size={21} />
                  </button>
                  <button
                    className="today-task-title"
                    onClick={() => onNavigate("matrix")}
                  >
                    <strong>{t.title}</strong>
                    <small>
                      {dueCaption(t.due_at)}
                      {t.important && " · 重要"}
                    </small>
                  </button>
                </div>
              ))}
              {!focus.length &&
                sectionState("tasks", "暂时没有待办，为今天留一件重要的事。")}
            </section>
            <section className="experience-card">
              <header>
                <h2>
                  <ShieldCheck size={17} />
                  需要你决定
                </h2>
                <button onClick={() => onAssistant("actions")}>
                  查看
                  <ArrowRight size={14} />
                </button>
              </header>
              {attention.slice(0, 3).map((a) => (
                <button
                  className="today-work"
                  key={a.id}
                  onClick={() => onAssistant("actions")}
                >
                  <span
                    className={`experience-status ${a.state === "UNKNOWN" ? "warning" : ""}`}
                  >
                    {a.state === "UNKNOWN" ? "待核对" : "待确认"}
                  </span>
                  <strong>
                    {a.kind === "calendar.update" ? "调整日历安排" : "发送邮件"}
                  </strong>
                  <small>
                    {a.state === "UNKNOWN"
                      ? "执行结果尚未确认，先核对，避免重复操作。"
                      : "查看具体内容后，再决定是否执行。"}
                  </small>
                </button>
              ))}
              {!attention.length &&
                sectionState("actions", "没有需要你确认的操作。")}
            </section>
            <section className="experience-card">
              <header>
                <h2>
                  <CalendarDays size={17} />
                  接下来
                </h2>
                <button onClick={() => onAssistant("connections")}>
                  日历
                  <ArrowRight size={14} />
                </button>
              </header>
              {agenda.items.slice(0, 5).map((item) => (
                <div className="today-work" key={item.id}>
                  <strong>{item.title}</strong>
                  <small>{agendaTime(item)}</small>
                </div>
              ))}
              {calendar.loading && !calendar.data && (
                <p className="experience-empty">正在读取日历…</p>
              )}
              {!!calendar.error && (
                <p className="experience-empty">
                  日历读取失败，请刷新重试；必要时重新授权连接。
                </p>
              )}
              {calendar.data && !calendar.data.connected && (
                <p className="experience-empty">
                  {calendar.data.blocked
                    ? "日历服务尚未配置（BLOCKED_EXTERNAL）。"
                    : "连接 Google Calendar 后，会议会显示在这里。"}
                </p>
              )}
              {calendar.data?.connected &&
                !agenda.items.length &&
                !calendar.error && (
                  <p className="experience-empty">未来七天没有会议安排。</p>
                )}
              {(calendar.data?.partial || agenda.invalid > 0) && (
                <p className="experience-empty">
                  日历结果不完整，请到原日历核对。
                </p>
              )}
            </section>
            <section className="experience-card">
              <header>
                <h2>
                  <Clock3 size={17} />
                  自动安排
                </h2>
                <button onClick={() => onNavigate("tasks")}>
                  自动任务
                  <ArrowRight size={14} />
                </button>
              </header>
              {upcoming.map((s) => (
                <button
                  className="today-work"
                  key={s.id}
                  onClick={() => onNavigate("tasks")}
                >
                  <strong>{s.title}</strong>
                  <small>
                    {new Date(s.next_fire_at!).toLocaleString("zh-CN", {
                      timeZone: s.timezone,
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}{" "}
                    · {s.timezone}
                  </small>
                </button>
              ))}
              {!upcoming.length &&
                sectionState("schedules", "还没有安排自动任务。")}
            </section>
            <section className="experience-card">
              <header>
                <h2>
                  <Sparkles size={17} />
                  助手发现
                </h2>
                <button onClick={() => onAssistant("suggestions")}>
                  建议
                  <ArrowRight size={14} />
                </button>
              </header>
              {data.signals?.slice(0, 2).map((s) => (
                <button
                  className="today-work"
                  key={s.id}
                  onClick={() => onAssistant("suggestions")}
                >
                  <span className="experience-status">
                    {s.kind === "CALENDAR_CONFLICT" ? "时间冲突" : "重要邮件"}
                  </span>
                  <strong>{s.suggestion}</strong>
                  <small>根据已连接服务的变化提出</small>
                </button>
              ))}
              {!data.signals?.length &&
                sectionState(
                  "signals",
                  data.connections?.availability === "BLOCKED_EXTERNAL"
                    ? "日历与邮件尚未接通，连接配置完成后才能发现变化。"
                    : "连接日历与邮件，重要变化会显示在这里。",
                )}
            </section>
          </div>
          <section className="experience-card today-running">
            <header>
              <h2>
                <Clock3 size={17} />
                交给 Adex 的事
              </h2>
              <button onClick={() => onNavigate("tasks")}>
                全部记录
                <ArrowRight size={14} />
              </button>
            </header>
            {activeRuns.slice(0, 3).map((r) => (
              <button
                className="today-run"
                key={r.id}
                onClick={() => onConversation(r.origin_conversation_id)}
              >
                <span
                  className={`experience-status ${r.status === "UNKNOWN" ? "warning" : ""}`}
                >
                  {runLabels[r.status] || r.status}
                </span>
                <strong>{r.instruction.slice(0, 100)}</strong>
                <ArrowRight size={16} />
              </button>
            ))}
            {!activeRuns.length &&
              sectionState(
                "runs",
                "当前没有后台工作。你可以随时安排研究、创作或提醒。",
              )}
          </section>
          <section className="experience-card">
            <header>
              <h2>
                <FolderOpen size={17} />
                最近的成果
              </h2>
              <button onClick={() => onNavigate("workspace")}>
                作品与文件
                <ArrowRight size={14} />
              </button>
            </header>
            <div className="today-artifacts">
              {data.artifacts?.slice(0, 3).map((a) => (
                <button key={a.id} onClick={() => onNavigate("workspace")}>
                  <FolderOpen size={19} />
                  <strong>{a.title}</strong>
                  <small>版本 {a.revision}</small>
                </button>
              ))}
            </div>
            {!data.artifacts?.length &&
              sectionState("artifacts", "报告、行程和创作结果，会在这里汇集。")}
          </section>
          {updated && (
            <p className="today-updated" role="status">
              更新于{" "}
              {updated.toLocaleTimeString("zh-CN", {
                hour: "2-digit",
                minute: "2-digit",
              })}
              {errors.length ? " · 部分内容暂不可用" : ""} ·
              到期日期按设备时区显示
            </p>
          )}
        </>
      )}
      <section className="today-ideas">
        <header>
          <h2>试着交给助手</h2>
          <p>从一句话开始，再一起完善。</p>
        </header>
        <div>
          {[
            {
              title: "规划一次旅行",
              text: "帮我规划一个四天三晚的旅行，先问我目的地、日期和预算。",
            },
            {
              title: "做一份深度研究",
              text: "帮我做一份深度研究报告，先和我确认研究主题与范围。",
            },
            {
              title: "安排每日简报",
              text: "每天早上八点帮我整理最新科技新闻，按北京时间执行。",
            },
          ].map((item) => (
            <button key={item.title} onClick={() => onPrompt(item.text)}>
              {item.title}
              <ArrowRight size={15} />
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
