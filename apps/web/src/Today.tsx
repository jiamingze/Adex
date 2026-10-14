import { usePageScroll } from "./usePageScroll";
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
  Clock3,
  Brain,
} from "lucide-react";
import { api, type Schedule, type Run, type Notification } from "./api";
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
  taskPriority,
  recentTaskResults,
  resultExcerpt,
} from "./todayModel";
import { native } from "./platform";
import { requestCalendarPermission } from "./nativeCalendar";
import { calendarResource } from "./calendarResource";
import { upcomingAgenda, agendaTime } from "./calendarAgenda";
import { todayReads } from "./todayReads";
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
  results: Notification[] | null;
  tasks: MatrixTask[] | null;
  schedules: Schedule[] | null;
  runs: Run[] | null;
  actions: Action[] | null;
  signals: Signal[] | null;
  connections: { items: { status: string }[]; availability: string } | null;
};
const empty: Data = {
  results: null,
  tasks: null,
  schedules: null,
  runs: null,
  actions: null,
  signals: null,
  connections: null,
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
  const pageScroll = usePageScroll<HTMLDivElement>("today");
  const calendar = useSyncExternalStore(
    calendarResource.subscribe,
    calendarResource.getSnapshot,
  );
  const agenda = upcomingAgenda(calendar.data?.events ?? []);
  const [data, setData] = useState<Data>(() => ({
    ...empty,
    tasks: guest ? null : (matrixResource.getSnapshot().data?.items ?? null),
    ...Object.fromEntries(
      Object.entries(todayReads).map(([key, resource]) => [
        key,
        guest
          ? null
          : key === "connections"
            ? resource.getSnapshot().data
            : (resource.getSnapshot().data?.items ?? null),
      ]),
    ),
  }));
  const [errors, setErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(!guest);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    if (guest) return;
    void calendarResource.load(native || revision > 0).catch(() => {});
    const refresh = () => {
      if (native && document.visibilityState === "visible") {
        calendarResource.invalidate();
        void calendarResource.load().catch(() => {});
      }
    };
    document.addEventListener("visibilitychange", refresh);
    return () => document.removeEventListener("visibilitychange", refresh);
  }, [guest, revision]);
  const [updated, setUpdated] = useState<Date | null>(null);
  const [planning, setPlanning] = useState(false);
  async function planToday() {
    if (guest) {
      onPrompt("");
      return;
    }
    if (planning) return;
    setPlanning(true);
    let cancelled = false;
    const cancel = () => {
      cancelled = true;
    };
    window.addEventListener("adex:session-changed", cancel);
    try {
      const [calendarRead, tasksRead, schedulesRead] = await Promise.allSettled(
        [
          calendarResource.load(true),
          matrixResource.load(),
          todayReads.schedules.load(),
        ],
      );
      if (cancelled) return;
      const value =
        calendarRead.status === "fulfilled" ? calendarRead.value : null;
      onPrompt(
        planningPrompt(
          {
            tasks:
              tasksRead.status === "fulfilled" ? tasksRead.value.items : null,
            schedules:
              schedulesRead.status === "fulfilled"
                ? schedulesRead.value.items
                : null,
            calendar: value
              ? {
                  events: value.events,
                  connected: value.connected,
                  partial: value.partial,
                }
              : { events: [], connected: false, partial: false, error: true },
          },
          new Date(),
        ),
      );
    } finally {
      window.removeEventListener("adex:session-changed", cancel);
      setPlanning(false);
    }
  }
  const [calendarAuthorizing, setCalendarAuthorizing] = useState(false);
  const [calendarPermissionError, setCalendarPermissionError] = useState("");
  async function authorizeCalendar() {
    setCalendarAuthorizing(true);
    setCalendarPermissionError("");
    let sessionChanged = false;
    const cancel = () => {
      sessionChanged = true;
    };
    window.addEventListener("adex:session-changed", cancel);
    try {
      await requestCalendarPermission();
      if (sessionChanged) return;
      calendarResource.invalidate();
      await calendarResource.load();
    } catch {
      setCalendarPermissionError("日历授权未完成，请重试。");
    } finally {
      window.removeEventListener("adex:session-changed", cancel);
      setCalendarAuthorizing(false);
    }
  }
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
    setErrors([]);
    const reads = { tasks: matrixResource, ...todayReads };
    let remaining = Object.keys(reads).length;
    // Each bounded read publishes immediately; a slow connector cannot block tasks.
    Object.entries(reads).forEach(([key, resource]) => {
      void resource
        .load(revision > 0)
        .then((value) => {
          if (!live) return;
          setData((previous) => ({
            ...previous,
            [key]: key === "connections" ? value : value.items,
          }));
          setUpdated(new Date());
        })
        .catch(() => {
          if (live) setErrors((previous) => [...previous, key]);
        })
        .finally(() => {
          if (live && --remaining === 0) setLoading(false);
        });
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
  const attention = awaitingAction(data.actions ?? []).sort(
    (a, b) => Number(b.state === "UNKNOWN") - Number(a.state === "UNKNOWN"),
  );
  const attentionRows = [
    ...attention.map((action) => ({ kind: "action" as const, action })),
    ...focus.map((task) => ({ kind: "task" as const, task })),
  ].slice(0, 5);
  const results = recentTaskResults(data.results ?? [], now).slice(0, 5);
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
    ) : data[key as keyof Data] === null && loading ? (
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
    <div ref={pageScroll} className="content-page today-page">
      <header className="today-heading">
        <div>
          <span className="experience-eyebrow">
            <Sun size={14} />
            {date}
          </span>
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
            <p>
              {guest
                ? "从一句话开始。"
                : "结合今天的日历和待办生成草稿，确认发送后交给助手。"}
            </p>
          </div>
        </div>
        <button
          onClick={() => void planToday()}
          disabled={planning}
          className="experience-primary"
        >
          {guest
            ? "和 Adex 聊聊"
            : planning
              ? "正在读取今日日程…"
              : "一起安排今天"}
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
                <p>登录后，任务、笔记和个人记忆都保存在你的账户中。</p>
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
            <section className="experience-card today-attention">
              <header>
                <h2>
                  <Circle size={17} />
                  待你处理
                </h2>
                <div className="attention-links">
                  <button onClick={() => onNavigate("matrix")}>待办</button>
                  <button onClick={() => onAssistant("actions")}>
                    审批
                    <ArrowRight size={14} />
                  </button>
                </div>
              </header>
              {taskError && (
                <p className="experience-inline-error" role="alert">
                  {taskError}
                </p>
              )}
              {attentionRows.map((row) =>
                row.kind === "task" ? (
                  (() => {
                    const t = row.task,
                      priority = taskPriority(t);
                    return (
                      <div className="attention-row" key={"task:" + t.id}>
                        <button
                          className="attention-check"
                          aria-label={`完成任务 ${t.title}`}
                          disabled={!!pending}
                          onClick={() => complete(t)}
                        >
                          <Circle size={17} />
                        </button>
                        <button
                          className="attention-title"
                          onClick={() => onNavigate("matrix")}
                        >
                          <strong>{t.title}</strong>
                          <small>{dueCaption(t.due_at)}</small>
                        </button>
                        <span className={`priority-tag ${priority.tone}`}>
                          {priority.label}
                        </span>
                      </div>
                    );
                  })()
                ) : (
                  <button
                    className="attention-row attention-action"
                    key={"action:" + row.action.id}
                    onClick={() => onAssistant("actions")}
                  >
                    <ShieldCheck size={17} />
                    <span className="attention-title">
                      <strong>
                        {row.action.kind === "calendar.update"
                          ? "调整日历安排"
                          : row.action.kind === "gmail.send"
                            ? "发送邮件"
                            : "确认助手操作"}
                      </strong>
                      <small>
                        {row.action.state === "UNKNOWN"
                          ? "核对执行结果，避免重复操作"
                          : "查看内容后决定是否执行"}
                      </small>
                    </span>
                    <span
                      className={`priority-tag ${row.action.state === "UNKNOWN" ? "critical" : "approval"}`}
                    >
                      {row.action.state === "UNKNOWN" ? "待核对" : "待确认"}
                    </span>
                  </button>
                ),
              )}
              {errors.includes("actions") && sectionState("actions", "")}
              {errors.includes("tasks") && sectionState("tasks", "")}
              {!attentionRows.length &&
                !errors.includes("actions") &&
                !errors.includes("tasks") && (
                  <p className="experience-empty">
                    {(data.tasks === null || data.actions === null) && loading
                      ? "正在读取待办与审批…"
                      : "暂时没有需要处理的事项。"}
                  </p>
                )}
              {focus.length + attention.length > 5 && (
                <p className="attention-more">
                  显示前 5 项 · 其余事项见待办或审批
                </p>
              )}
            </section>
            <section className="experience-card">
              <header>
                <h2>
                  <CalendarDays size={17} />
                  接下来
                </h2>
                <button
                  disabled={calendarAuthorizing}
                  onClick={() =>
                    native
                      ? void authorizeCalendar()
                      : onAssistant("connections")
                  }
                >
                  {native
                    ? calendarAuthorizing
                      ? "授权中…"
                      : "日历权限"
                    : "日历"}
                  <ArrowRight size={14} />
                </button>
              </header>
              {agenda.items.slice(0, 5).map((item) => (
                <div className="agenda-row" key={item.id}>
                  <div className="agenda-time">
                    <span>
                      {item.allDay
                        ? "全天"
                        : new Date(item.start).toLocaleTimeString("zh-CN", {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                    </span>
                    <small>
                      {new Date(item.start).toLocaleDateString("zh-CN", {
                        month: "numeric",
                        day: "numeric",
                      })}
                    </small>
                  </div>
                  <div className="agenda-main">
                    <strong>{item.title}</strong>
                    <small>
                      {item.ongoing ? "进行中 · " : ""}
                      {item.allDay
                        ? "全天事项"
                        : `至 ${new Date(item.end).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`}
                      {item.location ? ` · ${item.location}` : ""}
                    </small>
                    {(item.organizer || item.location) && (
                      <details>
                        <summary>会议详情</summary>
                        <p>{agendaTime(item)}</p>
                        {item.organizer && <p>邀请人：{item.organizer}</p>}
                        {item.location && <p>地点：{item.location}</p>}
                      </details>
                    )}
                  </div>
                </div>
              ))}
              {calendarPermissionError && (
                <p className="experience-empty">{calendarPermissionError}</p>
              )}
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
                  {native
                    ? calendar.data.permission === "DENIED"
                      ? "日历访问未授权，请到 iPhone 设置 → Adex 开启完整日历访问。"
                      : "点击日历权限，读取手机已同步的会议。iOS 需要完整访问权限，此功能只读取、不修改、不上传。"
                    : calendar.data.blocked
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
            <p className="result-window">
              最近 24 小时的执行结果 · 到期自动隐藏
            </p>
            {results.map((result) => (
              <button
                className="today-result"
                key={result.id}
                onClick={() => onConversation(result.conversation_id)}
              >
                <span className="result-mark">
                  <Check size={17} />
                </span>
                <span className="result-content">
                  <strong>
                    {(() => {
                      const run = data.runs?.find(
                        (run) => run.id === result.run_id,
                      );
                      return (
                        data.schedules?.find(
                          (schedule) => schedule.id === run?.schedule_id,
                        )?.title ||
                        run?.instruction.slice(0, 100) ||
                        result.title
                      );
                    })()}
                  </strong>
                  <span>
                    {resultExcerpt(result.body) ||
                      "结果已送达，打开原会话查看。"}
                  </span>
                  <small>
                    {new Date(result.created_at).toLocaleString("zh-CN", {
                      month: "numeric",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </small>
                </span>
                <ArrowRight size={15} />
              </button>
            ))}
            {!results.length &&
              sectionState(
                "results",
                "最近 24 小时没有新的任务执行结果。历史结果仍可在通知或原会话查看。",
              )}
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
