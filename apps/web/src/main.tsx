import { LocationConsent } from "./LocationConsent";
import { currentLocation, locationRelevant, locationPreference, type ClientLocation, type LocationMode } from "./locationContext";
import { matrixResource } from "./matrixResource";
import { noteView } from "./notesApi";
import { ReplyNoteAction } from "./ReplyNoteAction";
import { useChatScroll } from "./useChatScroll";
import { preferences } from "./preferences";
import { Cards } from "./Cards";
import React, { useEffect, useRef, useState, useDeferredValue } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowUp,
  ArrowRight,
  Brain,
  CalendarClock,
  Check,
  CirclePlus,
  Clock3,
  LogOut,
  MessageSquare,
  Pause,
  Play,
  Plus,
  Search,
  Sparkles,
  Trash2,
  X,
  Bell,
  Menu,
  ShieldCheck,
  Pencil,
  SquarePen,
  ChevronDown,
  Copy,
  RotateCcw,
  Quote,
  Square,
  Sun,
} from "lucide-react";
import { Markdown } from "./Markdown";
import { Button, Badge } from "@adex/ui-web";
import {
  api,
  ApiError,
  type Conversation,
  type Message,
  type Schedule,
  type Run,
  type Memory,
  type Notification,
} from "./api";
import type { components } from "../../../packages/contracts/core.generated";
import "./style.css";
import "./experience.css";
import { Today } from "./Today";
import {
  WorkspaceNavigation,
  MobileNavigation,
  AccountPrompt,
} from "./WorkspaceNavigation";
import {
  routeFromPath,
  pagePath,
  isPage,
  pageLabels,
  type Page,
} from "./navigation";
import { Notes } from "./Notes";
import { Tools } from "./Tools";
import { Settings } from "./Settings";
import { accountApi, workspaceApi } from "./api";
import { native, requestPush } from "./platform";
import { VoiceInput } from "./VoiceInput";
import { AttachmentMenu } from "./AttachmentMenu";
import { LiveResponse } from "./LiveResponse";
import { TaskMatrix } from "./TaskMatrix";
import { AssistantHub, type AssistantTab } from "./AssistantHub";
import { assistantApi } from "./assistantApi";
import { listenPush } from "./platform";
const statusText: Record<string, string> = {
  ACTIVE: "已启用",
  PAUSED: "已暂停",
  CANCELLED: "已取消",
  COMPLETED: "已完成",
  RUNNING: "执行中",
  QUEUED: "等待执行",
  WAITING_INPUT: "等待你处理",
  FAILED: "执行失败",
  UNKNOWN: "结果待核对",
};
const errorText: Record<string, string> = {
  DAILY_MODEL_BUDGET_EXCEEDED:
    "今日模型调用额度已用完。可在设置的用量页查看，请联系管理员调整额度或明天继续。",
  CHAT_TIMEOUT: "本次回复超时，已停止。你可以继续发送新问题。",
  UNSUPPORTED_TOOL_CALL: "模型返回了无效工具指令，请重新搜索。该指令未执行",
  MUSIC_NOT_CONFIGURED: "音乐生成服务尚未配置，请联系管理员",
  MUSIC_PROVIDER_DENIED: "音乐供应商拒绝请求，请检查音乐 API 权限或余额",
  MUSIC_PROVIDER_REJECTED: "音乐生成服务暂时不可用",
  INVALID_MEDIA_DURATION: "音乐时长需在 1–600 秒之间",
  USERNAME_TAKEN: "这个用户名已被使用",
  INVALID_USERNAME: "用户名需为 3–32 位字母、数字、下划线或短横线",
  SIGN_IN_REQUIRED: "请注册或登录后使用任务、附件与创作功能",
  GUEST_QUOTA_EXCEEDED: "今日访客额度已用完，请注册或登录继续",
  AUTH_RATE_LIMITED: "操作过于频繁，请稍后再试",
  INVALID_CREDENTIALS: "账号或密码不正确",
  CONVERSATION_BUSY: "当前会话正在回复，请稍后发送",
  PROVIDER_UNKNOWN: "模型调用结果未知，请核对后再发起新请求",
  PROVIDER_AUTH_FAILED: "模型认证失败，请检查服务端配置",
  PROVIDER_RATE_LIMIT: "模型服务限流，请稍后重试",
  MEMORY_TOMBSTONED: "这条记忆已被删除，系统已阻止重新写入",
  MEMORY_REVISION_CHANGED: "记忆已更新，本次旧上下文回复已停止",
  REVISION_CONFLICT: "任务已更新，正在刷新最新状态",
  DATABASE_UNAVAILABLE: "数据库暂不可用，请稍后重试",
  AGENT_UNAVAILABLE: "模型服务暂不可用",
  SCHEDULE_IN_PAST: "请选择未来的执行时间",
  LOGIN_RATE_LIMITED: "登录尝试过于频繁，请稍后重试",
};
function errorMessage(e: unknown) {
  return e instanceof ApiError
    ? errorText[e.code] || `操作失败（${e.code}）`
    : "连接失败，请检查服务状态";
}
function fmt(date: string | null, tz = "Asia/Shanghai") {
  if (!date) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: tz,
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(date));
}

let sessionBootstrap:
  | Promise<{ username: string; is_guest: boolean }>
  | undefined;
function chatFromUrl() {
  return routeFromPath(location.pathname).conversation;
}
function App() {
  const [assistantTab, setAssistantTab] = useState<AssistantTab>("suggestions");
  const [locationPrompt, setLocationPrompt] = useState(false);
  const locationChoice = useRef<{ conversation: string; resolve: (mode: LocationMode | null) => void } | null>(null);
  const [modelLabel, setModelLabel] = useState("");
  const [user, setUser] = useState("");
  const [guest, setGuest] = useState(false);
  const [ready, setReady] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);
  const [authRegister, setAuthRegister] = useState(false);
  const [page, setPage] = useState<Page>(
    () => routeFromPath(location.pathname).page,
  );
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [current, setCurrent] = useState(chatFromUrl);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loadedConversation, setLoadedConversation] = useState("");
  const messageCache = useRef(new Map<string, Message[]>());
  useEffect(() => {
    const clear = () => messageCache.current.clear();
    window.addEventListener("adex:session-changed", clear);
    return () => window.removeEventListener("adex:session-changed", clear);
  }, []);
  useEffect(() => {
    if (!current || loadedConversation !== current) return;
    messageCache.current.delete(current);
    messageCache.current.set(current, messages);
    if (messageCache.current.size > 5)
      messageCache.current.delete(messageCache.current.keys().next().value!);
  }, [current, loadedConversation, messages]);
  const [partial, setPartial] = useState("");
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [connected, setConnected] = useState(false);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [showSchedule, setShowSchedule] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [query, setQuery] = useState("");

  const [stopping, setStopping] = useState(false);
  const [chatError, setChatError] = useState("");
  const [failedTurns, setFailedTurns] = useState<Record<string, string>>({});
  const [deleteTarget, setDeleteTarget] = useState<Conversation | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [chatModel, setChatModel] = useState<"qwen3.8-max" | "minimax">(() =>
    localStorage.getItem("adex.chatModel") === "minimax"
      ? "minimax"
      : "qwen3.8-max",
  );
  const [progress, setProgress] = useState("正在理解你的问题");
  const [submitting, setSubmitting] = useState(false);
  const [optimistic, setOptimistic] = useState<
    (Message & { conv: string }) | null
  >(null);
  const followBottom = useRef(true);
  const chatScroll = useChatScroll(current, page === "chat", !current || loadedConversation === current, followBottom);
  const deferredPartial = useDeferredValue(partial);
  const [attachments, setAttachments] = useState<
    { id: string; name: string }[]
  >([]);
  const composerInput = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (!ready || guest || !native || !localStorage.getItem("adex.pushDevice")) return;
    // APNs tokens can rotate. Re-register previously enabled devices for the
    // authenticated owner; never turn notification preferences back on here.
    void requestPush().then(device => assistantApi.registerPush(device.token, device.environment))
      .then(result => localStorage.setItem("adex.pushDevice", result.id)).catch(() => {});
  }, [ready, guest]);
  const voiceSurface = useRef<HTMLButtonElement>(null);
  const [composerFocused, setComposerFocused] = useState(false);
  useEffect(() => {
    if (new URLSearchParams(location.search).get("connected") === "1") {
      setPage("assistant");
      history.replaceState({}, "", location.pathname);
    }
  }, []);
  useEffect(() => {
    if (!ready || guest) return;
    return listenPush(async (id) => {
      try {
        const result = await assistantApi.resume(id);
        setCurrent(result.conversation_id);
        setPage("chat");
        setMobile(false);
        setShowNotifications(false);
        setError("");
      } catch (e) {
        setError(errorMessage(e));
        throw e;
      }
    });
  }, [ready, guest]);
  useEffect(() => {
    const input = composerInput.current;
    if (input) {
      input.style.height = "auto";
      input.style.height = Math.min(input.scrollHeight, 144) + "px";
    }
  }, [draft, page, user]);
  const bottom = useRef<HTMLDivElement>(null);
  const sending = useRef(false);
  const pending = useRef<{
    id: string;
    content: string;
    conv: string;
    model: string;
    files: string[];
    clientLocation?: ClientLocation;
  } | null>(null);
  useEffect(() => {
    const handler = (event: Event) => {
      const value = (event as CustomEvent).detail;
      if (value==="browser") { setAssistantTab("browser");setPage("assistant"); }
      else if (isPage(value)) setPage(value);
    };
    window.addEventListener("adex:navigate", handler);
    return () => window.removeEventListener("adex:navigate", handler);
  }, []);
  const [hits, setHits] = useState<
    { id: string; conversation_id: string; content: string; title: string }[]
  >([]);
  useEffect(() => {
    let live = true;
    if (!query.trim() || !user) {
      setHits([]);
      return;
    }
    const timer = setTimeout(
      () =>
        accountApi
          .search(query)
          .then((r) => {
            if (live) setHits(r.items);
          })
          .catch(() => {}),
      350,
    );
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [query, user]);
  async function refreshConversations() {
    const r = await api.conversations();
    setConversations(r.items);
    return r.items;
  }
  async function refreshTasks() {
    const [s, r] = await Promise.all([api.schedules(), api.runs()]);
    setSchedules(s.items);
    setRuns(r.items);
  }
  async function refreshMemory() {
    setMemories((await api.memories()).items);
  }
  useEffect(() => {
    api
      .capabilities()
      .then((v) => setModelLabel(v.chat_model || ""))
      .catch(() => {});
  }, [user]);
  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const u = await (sessionBootstrap ??= (async () =>
          (await api.restore()) || (await api.guest()))());
        if (live) {
          setUser(u.username);
          setGuest(u.is_guest);
        }
      } catch (e) {
        if (live) setError(errorMessage(e));
      } finally {
        if (live) setReady(true);
      }
    })();
    return () => {
      live = false;
    };
  }, []);
  useEffect(() => {
    if (!user) return;
    const path = pagePath(page, current);
    if (location.pathname !== path) history.pushState({}, "", path);
  }, [current, page, user]);
  useEffect(() => {
    const back = () => {
      const route = routeFromPath(location.pathname);
      if (route.page === "chat") {
        setCurrent(route.conversation);
        if (!route.conversation) {
          setMessages([]);
          setPartial("");
          setOptimistic(null);
          setBusy(false);
        }
      }
      setPage(route.page);
      setMobile(false);
      setError("");
    };
    window.addEventListener("popstate", back);
    return () => window.removeEventListener("popstate", back);
  }, []);
  useEffect(() => {
    const reset = () => {
      setUser("");
      setCurrent("");
      setMessages([]);
    };
    window.addEventListener("adex:unauthorized", reset);
    return () => window.removeEventListener("adex:unauthorized", reset);
  }, []);
  useEffect(() => {
    if (!user) return;
    refreshConversations()
      .then((items) => {
        if (!chatFromUrl() && items[0]) setCurrent(items[0].id);
      })
      .catch((e) => setError(errorMessage(e)));
    const refresh = () =>
      api
        .notifications()
        .then((r) => setNotifications(r.items))
        .catch(() => {});
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, [user]);
  useEffect(() => {
    if (!user || guest || page !== "tasks") return;
    refreshTasks().catch((e) => setError(errorMessage(e)));
    const timer = setInterval(() => refreshTasks().catch(() => {}), 4000);
    return () => clearInterval(timer);
  }, [page, user, guest]);
  useEffect(() => {
    if (user && !guest && page === "memory")
      refreshMemory().catch((e) => setError(errorMessage(e)));
  }, [page, user, guest]);
  useEffect(() => {
    if (!current || !user) return;
    const controller = new AbortController();
    let after = 0;
    let cancelled = false;
    const cachedMessages = messageCache.current.get(current);
    setLoadedConversation(cachedMessages ? current : "");
    setMessages(cachedMessages ?? []);
    setFailedTurns({});
    setChatError("");
    setError("");
    setPartial("");
    setBusy(false);
    setConnected(false);
    (async () => {
      try {
        // Fetch the tail first so a push result is visible after one App request.
        let snap = await api.messages(current, 0, true);
        if (cancelled) return;
        setMessages(snap.items);
        setLoadedConversation(current);
        let all: Message[] = [...snap.items];
        if (snap.items.length === 200) {
          all = [];
          let cursor = 0;
          do {
            snap = await api.messages(current, cursor);
            all.push(...snap.items);
            if (snap.items.length) cursor = snap.items.at(-1)!.seq;
          } while (snap.items.length === 200 && !cancelled);
        }
        if (cancelled) return;
        setMessages(all);
        setLoadedConversation(current);
        setFailedTurns(
          Object.fromEntries(
            snap.turns
              .filter((t) => t.status === "FAILED")
              .map((t) => [
                t.id,
                errorText[t.error_code || ""] || "回复未完成，请重试",
              ]),
          ),
        );
        setBusy(
          snap.turns.some((t) => ["QUEUED", "RUNNING"].includes(t.status)),
        );
        after = snap.event_seq;
        setProgress(snap.progress || "正在思考回答");
        while (!cancelled) {
          try {
            setConnected(true);
            await api.stream(
              current,
              after,
              controller.signal,
              (type, data, seq) => {
                if (seq <= after) return;
                after = seq;
                if (type === "turn.started") {
                  setPartial("");
                  setBusy(true);
                }
                if (type === "turn.progress")
                  setProgress(String(data.text || "正在思考回答"));
                if (type === "token.delta")
                  setPartial((p) => p + String(data.text || ""));
                if (type === "message.committed") {
                  const m = {
                    id: String(data.message_id),
                    seq: Number(data.seq),
                    role: data.role as Message["role"],
                    content: String(data.content),
                  };
                  setMessages((prev) =>
                    prev.some((x) => x.id === m.id)
                      ? prev
                      : [...prev, m].sort((a, b) => a.seq - b.seq),
                  );
                  if (m.role === "assistant") setPartial("");
                }
                if (type === "turn.cancelled") {
                  setBusy(false);
                  setPartial("");
                }
                if (type === "message.cards") {
                  api
                    .messages(current)
                    .then((s) => {
                      if (!cancelled) setMessages(s.items);
                    })
                    .catch(() => {});
                }
                if (type === "turn.completed") {
                  setBusy(false);
                  setPartial("");
                  api
                    .messages(current)
                    .then((s) => {
                      if (!cancelled) setMessages(s.items);
                    })
                    .catch(() => {});
                }
                if (type === "turn.failed") {
                  setBusy(false);
                  setPartial("");
                  setFailedTurns((previous) => ({
                    ...previous,
                    [String(data.turn_id)]:
                      errorText[String(data.code)] || "回复未完成，请重试",
                  }));
                }
              },
            );
          } catch (e) {
            if (cancelled) break;
            setConnected(false);
          }
          if (!cancelled) await new Promise((r) => setTimeout(r, 1500));
        }
      } catch (e) {
        if (!cancelled) {
          if (e instanceof ApiError && [403, 404].includes(e.status)) {
            messageCache.current.delete(current);
            setMessages([]);
            setLoadedConversation("");
            setCurrent("");
            setOptimistic(null);
            setError("");
          } else setError(errorMessage(e));
        }
      }
    })();
    let polling = false;
    const poll =
      native || location.hostname.endsWith(".trycloudflare.com")
        ? setInterval(
            async () => {
              if (polling || cancelled) return;
              polling = true;
              try {
                const snap = await api.messages(current);
                if (cancelled) return;
                after = Math.max(after, snap.event_seq);
                setMessages((previous) => {
                  const merged = new Map(previous.map((m) => [m.id, m]));
                  snap.items.forEach((m) => merged.set(m.id, m));
                  const next = [...merged.values()].sort(
                    (a, b) => a.seq - b.seq,
                  );
                  return JSON.stringify(previous) === JSON.stringify(next)
                    ? previous
                    : next;
                });
                const running = snap.turns.some((t) =>
                  ["QUEUED", "RUNNING"].includes(t.status),
                );
                setBusy(running);
                if (snap.progress) setProgress(snap.progress);
                setPartial(running ? snap.partial || "" : "");
                setFailedTurns(
                  Object.fromEntries(
                    snap.turns
                      .filter((t) => t.status === "FAILED")
                      .map((t) => [
                        t.id,
                        errorText[t.error_code || ""] || "回复未完成，请重试",
                      ]),
                  ),
                );
              } catch {
              } finally {
                polling = false;
              }
            },
            native ? 500 : 3000,
          )
        : undefined;
    return () => {
      cancelled = true;
      controller.abort();
      if (poll) clearInterval(poll);
    };
  }, [current, user]);
  useEffect(() => {
    const scroller = bottom.current?.closest(".chat-scroll");
    if (scroller && followBottom.current) {
      const frame = requestAnimationFrame(() =>
        scroller.scrollTo({ top: scroller.scrollHeight, behavior: "instant" }),
      );
      return () => cancelAnimationFrame(frame);
    }
  }, [messages, deferredPartial, optimistic, page, current, loadedConversation]);
  useEffect(() => {
    // Chat actions may create todos server-side; refresh the shared projection
    // when a reply finishes so Today/Todos do not retain the pre-action cache.
    if (user && !guest && !busy) void matrixResource.load(true).catch(() => {});
  }, [busy, user, guest]);
  useEffect(() => {
    const request = locationChoice.current;
    if (request && (!user || page !== "chat" || current !== request.conversation)) {
      locationChoice.current = null;
      setLocationPrompt(false);
      request.resolve(null);
    }
  }, [page, current, user]);
  async function newConversation() {
    try {
      const c = await api.createConversation("新对话");
      setConversations((p) => [c, ...p]);
      setCurrent(c.id);
      setPage("chat");
      setMobile(false);
      setDraft("");
      setAttachments([]);
      setOptimistic(null);
      followBottom.current = true;
      setError("");
    } catch (e) {
      setError(errorMessage(e));
    }
  }
  async function send(replacement?: string) {
    const text = typeof replacement === "string" ? replacement : draft;
    if (!text.trim() || sending.current || busy) return;
    sending.current = true;
    setSubmitting(true);
    followBottom.current = true;
    setError("");
    setChatError("");
    const content = text.trim();
    const files = attachments.map((f) => f.id);
    if (typeof replacement !== "string") setDraft("");
    let conv = current;
    try {
      if (!conv) {
        const c = await api.createConversation(content.slice(0, 24));
        setConversations((p) => [c, ...p]);
        setCurrent(c.id);
        conv = c.id;
      }
      let logical = pending.current;
      if (
        !logical ||
        logical.content !== content ||
        logical.conv !== conv ||
        logical.model !== chatModel ||
        JSON.stringify(logical.files) !== JSON.stringify(files)
      ) {
        logical = {
          id: crypto.randomUUID(),
          content,
          conv,
          model: chatModel,
          files,
        };
        if (locationRelevant(content)) {
          // Show the user's question before asking for location in the same chat.
          // No model invocation or location access happens before this consent.
          setOptimistic({
            id: logical.id,
            seq: Math.max(0, ...messages.map((m) => m.seq)) + 1,
            role: "user",
            content,
            conv,
          });
          if (!locationPreference().mode || locationPreference().mode === "manual") {
            setLocationPrompt(true);
            const choice = await new Promise<LocationMode | null>((resolve) => {
              locationChoice.current = { conversation: conv, resolve };
            });
            if (choice === null) throw new DOMException("Location request cancelled", "AbortError");
          }
          setProgress("正在准备查询");
          logical.clientLocation = await currentLocation();
        }
        pending.current = logical;
      }
      setOptimistic({
        id: logical.id,
        seq: Math.max(0, ...messages.map((m) => m.seq)) + 1,
        role: "user",
        content,
        conv,
      });
      setProgress("正在理解你的问题");
      setBusy(true);
      const accepted = await api.send(conv, {
        client_message_id: logical.id,
        content,
        file_ids: files,
        model: chatModel,
        client_location: logical.clientLocation,
      });
      setBusy(true);
      setOptimistic((previous) =>
        previous ? { ...previous, id: accepted.message_id } : null,
      );
      pending.current = null;
      setAttachments([]);
      void refreshConversations().catch(() => {});
    } catch (e) {
      setBusy(false);
      setOptimistic(null);
      if (e instanceof DOMException && e.name === "AbortError") return;
      // Keep recognized speech as an editable draft if the network send fails.
      setDraft((existing) => existing || text);
      setChatError(errorMessage(e));
    } finally {
      sending.current = false;
      setSubmitting(false);
    }
  }
  async function changeSchedule(s: Schedule, status: string) {
    try {
      await api.updateSchedule(s, status);
      await refreshTasks();
    } catch (e) {
      setError(errorMessage(e));
      await refreshTasks().catch(() => {});
    }
  }
  async function remember(content: string) {
    try {
      await api.remember(content);
      await refreshMemory();
    } catch (e) {
      setError(errorMessage(e));
    }
  }
  if (!ready) return native ? (
    <div className="native-launch" role="status" aria-label="正在打开 Adex，让智能，成为日常。">
      <img src="/brand/adex-launch.png" alt="" />
    </div>
  ) : <div className="session-loading">正在打开 Adex…</div>;
  if (!user)
    return (
      <Login
        onLogin={(name, isGuest = false) => {
          setUser(name);
          setGuest(isGuest);
        }}
        onGuest={async () => {
          const u = await api.guest();
          setUser(u.username);
          setGuest(u.is_guest);
        }}
      />
    );
  const selected = conversations.find((c) => c.id === current);
  const unread = notifications.filter((n) => !n.read).length;
  return (
    <div className="shell">
      <aside className={`sidebar ${mobile ? "open" : ""}`}>
        <div className="brand">
          <div className="brand-icon">
            <img src="/brand/adex-icon.png" alt="" width={30} height={30} />
          </div>
          <strong>
            Adex<span> /</span>
          </strong>
          <button
            className="mobile-close icon-button"
            onClick={() => setMobile(false)}
            aria-label="关闭导航"
          >
            <X size={18} />
          </button>
        </div>
        <Button className="new-chat" onClick={newConversation}>
          <Plus size={16} /> 开始新对话 <span>⌘</span>
        </Button>
        <WorkspaceNavigation
          page={page}
          onNavigate={(p) => {
            setPage(p);
            setMobile(false);
            setError("");
          }}
        />
        <div className="history-heading">
          <span className="section-label">最近对话</span>
          <Search size={14} />
        </div>
        <input
          className="history-search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="查找会话…"
          aria-label="查找会话"
        />
        {query &&
          hits.map((hit) => (
            <button
              className="history-item"
              key={hit.id}
              onClick={() => {
                setCurrent(hit.conversation_id);
                setPage("chat");
                setMobile(false);
              }}
            >
              <span>
                {hit.title}
                <small>{hit.content.slice(0, 70)}</small>
              </span>
            </button>
          ))}
        <div className="history">
          {conversations
            .filter((c) => c.title.includes(query))
            .map((c) => (
              <div
                key={c.id}
                className={
                  c.id === current && page === "chat"
                    ? "history-row selected"
                    : "history-row"
                }
              >
                <button
                  className="history-item"
                  onClick={() => {
                    setCurrent(c.id);
                    setPage("chat");
                    setMobile(false);
                  }}
                >
                  <MessageSquare size={14} />
                  <span>{c.title}</span>
                </button>
                <button
                  className="history-delete icon-button"
                  aria-label={`删除会话：${c.title}`}
                  onClick={() => setDeleteTarget(c)}
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          {!conversations.length && (
            <div className="empty-history">你的下一段对话，从这里开始。</div>
          )}
        </div>
        <div className="sidebar-bottom">
          {guest && (
            <div className="sidebar-auth">
              <Button
                className="primary"
                onClick={() => {
                  setMobile(false);
                  setAuthRegister(false);
                  setAuthOpen(true);
                }}
              >
                登录
              </Button>
              <Button
                onClick={() => {
                  setMobile(false);
                  setAuthRegister(true);
                  setAuthOpen(true);
                }}
              >
                注册
              </Button>
            </div>
          )}
          <div className="private-note">
            <ShieldCheck size={15} /> 你的个人工作空间
          </div>
          <div className="profile">
            <div className="avatar">
              {guest ? "A" : user.slice(0, 1).toUpperCase()}
            </div>
            <div>
              <strong>{guest ? "访客" : user}</strong>
              <small>{guest ? "当前设备的访客空间" : "个人账户"}</small>
            </div>
            <button
              className="icon-button"
              aria-label="退出登录"
              onClick={async () => {
                await api.logout();
                setCurrent("");
                setMessages([]);
                setConversations([]);
                history.replaceState({}, "", "/");
                const u = await api.guest();
                setUser(u.username);
                setGuest(u.is_guest);
              }}
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>
      {mobile && <div className="backdrop" onClick={() => setMobile(false)} />}
      <main className="main">
        <header className={`topbar ${page === "chat" ? "chat-topbar" : ""}`}>
          <div className="breadcrumb">
            <button
              className="mobile-menu icon-button"
              aria-label="打开导航"
              onClick={() => {
                (document.activeElement as HTMLElement)?.blur();
                setMobile(true);
              }}
            >
              <Menu size={20} />
            </button>
            {page === "chat" ? (
              <label className="chat-model-picker">
                <span className="sr-only">聊天模型</span>
                <select
                  aria-label="聊天模型"
                  value={chatModel}
                  disabled={busy || submitting}
                  onChange={(e) => {
                    const model = e.target.value as typeof chatModel;
                    setChatModel(model);
                    localStorage.setItem("adex.chatModel", model);
                  }}
                >
                  <option value="qwen3.8-max">Qwen 3.8 Max</option>
                  <option value="minimax">MiniMax</option>
                </select>
                <ChevronDown size={14} />
              </label>
            ) : (
              <span role="heading" aria-level={1}>{page === "today" ? "Today" : page === "matrix" ? "Todo" : pageLabels[page]}</span>
            )}
          </div>
          <div className="top-actions">
            <button
              className="icon-button today-shortcut"
              aria-label="今日概览"
              onClick={() => {
                setPage("today");
                setError("");
              }}
            >
              <Sun size={20} />
            </button>
            <button
              className="icon-button header-new-chat"
              aria-label="新建聊天"
              onClick={newConversation}
            >
              <SquarePen size={22} />
            </button>
            {guest && (
              <>
                <button
                  className="text-button"
                  onClick={() => {
                    setAuthRegister(false);
                    setAuthOpen(true);
                  }}
                >
                  登录
                </button>
                <Button
                  onClick={() => {
                    setAuthRegister(true);
                    setAuthOpen(true);
                  }}
                >
                  注册
                </Button>
              </>
            )}
            <span className="model-label">
              <span className="green-dot" />
              {modelLabel || "AI 助手"}
            </span>
            <button
              className="notification-button icon-button"
              aria-label="通知"
              onClick={() => setShowNotifications(!showNotifications)}
            >
              <Bell size={18} />
              {unread > 0 && <i />}
            </button>
          </div>
        </header>
        {error && (
          <div className="error-banner" role="alert">
            {error}
            <button
              className="icon-button"
              aria-label="关闭提示"
              onClick={() => setError("")}
            >
              <X size={15} />
            </button>
          </div>
        )}
        {page === "today" && (
          <Today
            onAssistant={(tab) => {
              setAssistantTab(tab);
              setPage("assistant");
            }}
            guest={guest}
            username={user}
            onNavigate={(p) => {
              setPage(p);
              setError("");
            }}
            onConversation={(id) => {
              setCurrent(id);
              setPage("chat");
            }}
            onPrompt={(text) => {
              setCurrent("");
              setMessages([]);
              setPartial("");
              setBusy(false);
              setOptimistic(null);
              setAttachments([]);
              setChatError("");
              setPage("chat");
              setDraft(text);
            }}
            onSignIn={() => {
              setAuthRegister(false);
              setAuthOpen(true);
            }}
          />
        )}
        {guest &&
          [
            "matrix",
            "assistant",
            "tasks",
            "workspace",
            "tools",
            "memory",
          ].includes(page) && (
            <AccountPrompt
              onSignIn={() => {
                setAuthRegister(false);
                setAuthOpen(true);
              }}
            />
          )}
        {page === "chat" && (
          <div className="chat-page">
            <div
              className="chat-scroll"
              ref={chatScroll.ref}
              onScroll={chatScroll.onScroll}
            >
              {messages.length === 0 &&
              (!optimistic || optimistic.conv !== current) &&
              !busy &&
              !submitting ? (
                <div className="welcome">
                  <div className="eyebrow">
                    <span /> 你的个人助手
                  </div>
                  <h1>今天有什么可以帮你？</h1>
                  <p>聊聊想法，或把下一件事交给我。</p>
                  <button
                    className="welcome-today"
                    onClick={() => setPage("today")}
                  >
                    <Sun size={15} />
                    看看今日概览
                    <ArrowRight size={14} />
                  </button>
                  <div className="welcome-cards">
                    <button
                      onClick={() => setDraft("帮我梳理今天最重要的三件事")}
                    >
                      <MessageSquare size={20} />
                      <strong>从一个想法开始</strong>
                      <span>整理思路，让问题更清晰</span>
                      <ArrowRight size={16} />
                    </button>
                    <button
                      onClick={() => {
                        setPage("tasks");
                        setShowSchedule(true);
                      }}
                    >
                      <CalendarClock size={20} />
                      <strong>让事情按时发生</strong>
                      <span>创建提醒，安排周期任务</span>
                      <ArrowRight size={16} />
                    </button>
                    <button onClick={() => setPage("memory")}>
                      <Brain size={20} />
                      <strong>记住你的偏好</strong>
                      <span>查看、纠正和管理长期记忆</span>
                      <ArrowRight size={16} />
                    </button>
                  </div>
                  <div className="welcome-caption">
                    <ShieldCheck size={13} /> 聊天和任务结果会保存在你的工作空间
                  </div>
                </div>
              ) : (
                <div className="transcript">
                  <div className="conversation-title">
                    {selected?.title || "新对话"}{" "}
                    <button
                      className="text-button"
                      onClick={async () => {
                        const title = window.prompt(
                          "会话名称",
                          selected?.title,
                        );
                        if (title) {
                          await accountApi.rename(current, title);
                          await refreshConversations();
                        }
                      }}
                    >
                      重命名
                    </button>
                    <button
                      className="text-button"
                      onClick={() =>
                        setDeleteTarget(
                          selected || {
                            id: current,
                            title: "当前会话",
                            created_at: "",
                          },
                        )
                      }
                    >
                      删除
                    </button>
                  </div>
                  {[
                    ...messages,
                    ...(optimistic &&
                    optimistic.conv === current &&
                    !messages.some(
                      (m) =>
                        m.id === optimistic.id ||
                        (m.seq === optimistic.seq &&
                          m.content === optimistic.content),
                    )
                      ? [optimistic]
                      : []),
                  ].map((m) => (
                    <article key={m.id} className={`message ${m.role}`}>
                      <div className="message-avatar">
                        {m.role === "user" ? (
                          user.slice(0, 1).toUpperCase()
                        ) : (
                          <Sparkles size={16} />
                        )}
                      </div>
                      <div className="message-content">
                        <div className="message-label">
                          {m.role === "user" ? "你" : "Adex"}
                        </div>
                        {/minimax:tool_call|<invoke\b|\[TOOL_CALL\]|<tool_call/i.test(
                          m.content,
                        ) ? (
                          <div className="form-error">
                            这条回复包含无效的工具指令，搜索未实际完成。请点击重新生成再次搜索。
                          </div>
                        ) : (
                          <Markdown content={m.content} />
                        )}
                        <Cards cards={m.cards || []} />
                        {failedTurns[m.id] && (
                          <div className="reply-failure" role="status">
                            <p>{failedTurns[m.id]}</p>
                            <button
                              className="text-button"
                              disabled={busy}
                              onClick={() => send(m.content)}
                            >
                              重新回复
                            </button>
                          </div>
                        )}
                        <button
                          className="text-button"
                          onClick={() =>
                            setDraft(
                              "引用：" + m.content.slice(0, 1000) + "\n\n",
                            )
                          }
                          aria-label="引用回复"
                        >
                          <Quote size={16} />
                        </button>
                        {m.role === "assistant" && (
                          <button
                            className="text-button"
                            disabled={busy}
                            onClick={() =>
                              send(
                                messages
                                  .slice(
                                    0,
                                    messages.findIndex((x) => x.id === m.id),
                                  )
                                  .reverse()
                                  .find((x) => x.role === "user")?.content ||
                                  "请重新回答并核实依据。",
                              )
                            }
                            aria-label="重新生成"
                          >
                            <RotateCcw size={16} />
                          </button>
                        )}
                        {m.role === "assistant" && (
                          <button
                            className="text-button"
                            aria-label="复制回复"
                            onClick={async () => {
                              try {
                                await navigator.clipboard.writeText(m.content);
                                setError("");
                              } catch {
                                setError("复制失败，请长按文字复制");
                              }
                            }}
                          >
                            <Copy size={16} />
                          </button>
                        )}
                        {m.role === "assistant" && <ReplyNoteAction conversation={current} message={m.id} guest={guest} onSignIn={()=>{setAuthRegister(false);setAuthOpen(true);}} onOpen={id=>{noteView.selected=id;noteView.query="";setPage("workspace");}}/>}
                      </div>
                    </article>
                  ))}
                  {locationPrompt ? (
                    <LocationConsent onChoose={(mode) => {
                      setLocationPrompt(false);
                      locationChoice.current?.resolve(mode);
                      locationChoice.current = null;
                    }} />
                  ) : (busy || submitting) && (
                    <article className="message assistant">
                      <div className="message-avatar">
                        <Sparkles size={16} />
                      </div>
                      <div className="message-content">
                        <div className="message-label">Adex</div>
                        {partial ? (
                          <LiveResponse content={deferredPartial} />
                        ) : (
                          <div className="thinking">
                            <span />
                            <span />
                            <span /> {progress}
                          </div>
                        )}
                      </div>
                    </article>
                  )}
                  <div ref={bottom} />
                  {chatError && (
                    <div className="reply-failure" role="status">
                      {chatError}
                      <button
                        className="text-button"
                        onClick={() => setChatError("")}
                      >
                        关闭
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="composer-wrap">
              <div className={`composer ${!draft && !attachments.length ? "composer-empty" : ""} ${busy ? "composer-busy" : ""}`}>
                <div className="composer-entry">
                  <textarea
                    ref={composerInput}
                    onFocus={() => setComposerFocused(true)}
                    onBlur={() => setComposerFocused(false)}
                    aria-label="消息输入"
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    placeholder="按住说话，或点按输入"
                    rows={1}
                    maxLength={16000}
                    onKeyDown={(e) => {
                      if (
                        e.key === "Enter" &&
                        !e.shiftKey &&
                        !e.nativeEvent.isComposing &&
                        (preferences().enterSend || e.ctrlKey || e.metaKey)
                      ) {
                        e.preventDefault();
                        send();
                      }
                    }}
                  />
                  <button
                    ref={voiceSurface}
                    type="button"
                    className="composer-voice-surface"
                    hidden={!!draft || composerFocused || busy || !!attachments.length}
                    aria-label="按住说话，或点按输入"
                    onClick={(event) => {
                      // Keyboard/screen-reader activation enters text editing.
                      // Pointer gestures are owned by VoiceInput, including release.
                      if (event.detail === 0) composerInput.current?.focus();
                    }}
                  >按住说话，或点按输入</button>
                </div>
                <div className="attachment-chips">
                  {attachments.map((f) => (
                    <button
                      className="text-button"
                      key={f.id}
                      onClick={() =>
                        setAttachments((a) => a.filter((x) => x.id !== f.id))
                      }
                    >
                      {f.name} ×
                    </button>
                  ))}
                </div>
                <div className="composer-actions">
                  <AttachmentMenu
                    guest={guest}
                    onSignIn={() => {
                      setAuthRegister(true);
                      setAuthOpen(true);
                    }}
                    onFile={async (file, key) => {
                      try {
                        const stored = await workspaceApi.upload(file, key);
                        setAttachments((a) => [...a, stored].slice(-5));
                      } catch (error) {
                        throw new Error(
                          error instanceof ApiError
                            ? errorMessage(error)
                            : error instanceof Error
                              ? error.message
                              : errorMessage(error),
                        );
                      }
                    }}
                  />
                  <div className="composer-right">
                    <VoiceInput
                      key={`${current}:${page}:${mobile}`}
                      surfaceRef={voiceSurface}
                      inputRef={composerInput}
                      hasText={draft.length > 0 || busy}
                      onText={(text) => {
                        if (busy || sending.current) setDraft((d) => d + text);
                        else void send(text);
                      }}
                    />
                    <span>Enter 发送</span>
                    <button
                      className="send-button"
                      aria-label={busy ? "停止生成" : "发送消息"}
                      disabled={busy ? stopping : submitting || !draft.trim()}
                      onClick={async () => {
                        if (!busy) {
                          send();
                          return;
                        }
                        if (stopping) return;
                        setStopping(true);
                        try {
                          await accountApi.stop(current);
                          setBusy(false);
                          setPartial("");
                          setProgress("");
                        } catch (e) {
                          setChatError(errorMessage(e));
                        } finally {
                          setStopping(false);
                        }
                      }}
                    >
                      {busy ? (
                        <Square size={15} fill="currentColor" />
                      ) : (
                        <ArrowUp size={18} />
                      )}
                    </button>
                  </div>
                </div>
              </div>
              <div className="composer-caption">
                <span
                  className={connected ? "connection connected" : "connection"}
                >
                  {connected
                    ? "已连接 · 对话自动保存"
                    : "连接中 · 结果可从历史恢复"}
                </span>
              </div>
            </div>
          </div>
        )}
        {!guest && page === "tasks" && (
          <div className="content-page">
            <div className="page-heading">
              <div>
                <p>安排一次提醒，或把重复的事交给后台。</p>
              </div>
              <Button className="primary" onClick={() => setShowSchedule(true)}>
                <Plus size={17} />
                新建任务
              </Button>
            </div>
            <div className="stat-grid">
              <div>
                <span>正在安排</span>
                <strong>
                  {schedules.filter((s) => s.status === "ACTIVE").length}
                  <small>项任务</small>
                </strong>
              </div>
              <div>
                <span>正在执行</span>
                <strong>
                  {runs.filter((r) => r.status === "RUNNING").length}
                  <small>项任务</small>
                </strong>
              </div>
              <div>
                <span>已完成</span>
                <strong>
                  {runs.filter((r) => r.status === "COMPLETED").length}
                  <small>次执行</small>
                </strong>
              </div>
            </div>
            <div className="list-heading">
              <h2>我的日程</h2>
              <span>离开页面后，后台继续执行</span>
            </div>
            <div className="schedule-list">
              {!schedules.length && (
                <Empty
                  icon={<CalendarClock size={26} />}
                  title="为未来留一个安排"
                  text="创建你的第一个定时任务，结果会回到原对话。"
                />
              )}
              {schedules.map((s) => (
                <div className="schedule-row" key={s.id}>
                  <div className="row-icon">
                    <CalendarClock size={20} />
                  </div>
                  <div className="row-main">
                    <strong>{s.title}</strong>
                    <p>{s.instruction}</p>
                    <div className="row-meta">
                      <span>
                        <Clock3 size={12} />
                        {s.kind === "DAILY"
                          ? "每天"
                          : s.kind === "INTERVAL"
                            ? "周期执行"
                            : "一次性"}{" "}
                        · {s.timezone}
                      </span>
                      <span>下次：{fmt(s.next_fire_at, s.timezone)}</span>
                    </div>
                  </div>
                  <Badge tone={s.status === "ACTIVE" ? "green" : "muted"}>
                    {statusText[s.status]}
                  </Badge>
                  {["ACTIVE", "PAUSED"].includes(s.status) && (
                    <div className="schedule-actions" role="group" aria-label="任务操作">
                      <button
                        className="icon-button"
                        aria-label={
                          s.status === "ACTIVE" ? "暂停任务" : "恢复任务"
                        }
                        onClick={() =>
                          changeSchedule(
                            s,
                            s.status === "ACTIVE" ? "PAUSED" : "ACTIVE",
                          )
                        }
                      >
                        {s.status === "ACTIVE" ? (
                          <Pause size={17} />
                        ) : (
                          <Play size={17} />
                        )}
                      </button>
                      <button
                        className="icon-button"
                        aria-label="取消日程"
                        onClick={() => changeSchedule(s, "CANCELLED")}
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
            <div className="list-heading">
              <h2>运行记录</h2>
              <span>查看结果与恢复状态</span>
            </div>
            <div className="run-list">
              {runs.length === 0 ? (
                <p className="muted-text">任务首次执行后，记录会出现在这里。</p>
              ) : (
                runs.map((r) => (
                  <div className="run-row" key={r.id}>
                    <div>
                      <strong>{r.instruction.slice(0, 70)}</strong>
                      <small>
                        {fmt(r.created_at)}
                        {r.checkpoint_ref ? " · 已保存恢复点" : ""}
                        {r.error_code
                          ? " · " + (errorText[r.error_code] || r.error_code)
                          : ""}
                      </small>
                    </div>
                    <Badge
                      tone={
                        r.status === "COMPLETED"
                          ? "green"
                          : r.status === "FAILED" || r.status === "UNKNOWN"
                            ? "red"
                            : "muted"
                      }
                    >
                      {statusText[r.status] || r.status}
                    </Badge>
                    {["QUEUED", "RUNNING"].includes(r.status) && (
                      <button
                        className="icon-button"
                        aria-label="取消本次执行"
                        onClick={async () => {
                          try {
                            await api.cancelRun(r.id);
                            await refreshTasks();
                          } catch (e) {
                            setError(errorMessage(e));
                          }
                        }}
                      >
                        <X size={16} />
                      </button>
                    )}
                    <button
                      className="text-button"
                      onClick={() => {
                        setCurrent(r.origin_conversation_id);
                        setPage("chat");
                      }}
                    >
                      查看对话 <ArrowRight size={13} />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
        {page === "settings" && (
          <Settings
            conversations={conversations}
            guest={guest}
            onSignIn={() => {
              setAuthRegister(false);
              setAuthOpen(true);
            }}
            onNavigate={setPage}
            onAssistant={(tab) => {
              setAssistantTab(tab);
              setPage("assistant");
            }}
          />
        )}
        {!guest && page === "matrix" && <TaskMatrix />}
        {!guest && page === "assistant" && (
          <AssistantHub
            initialTab={assistantTab}
            conversation={current}
            onConversationCreated={(c) => {
              setCurrent(c.id);
              setConversations((list) => [c, ...list]);
            }}
          />
        )}
        {!guest && page === "tools" && <Tools conversation={current} />}
        {!guest && page === "workspace" && (
          <Notes />
        )}
        {!guest && page === "memory" && (
          <MemoryPage
            memories={memories}
            onAdd={remember}
            onDelete={async (id) => {
              try {
                await api.forget(id);
                await refreshMemory();
              } catch (e) {
                setError(errorMessage(e));
              }
            }}
            onCorrect={async (id, content) => {
              try {
                await api.correctMemory(id, content);
                await refreshMemory();
              } catch (e) {
                setError(errorMessage(e));
              }
            }}
          />
        )}
        <MobileNavigation
          page={page}
          onNavigate={(p) => {
            setPage(p);
            setMobile(false);
            setError("");
          }}
        />
        {showNotifications && (
          <div className="notifications">
            <div className="list-heading">
              <h2>通知</h2>
              <button
                className="icon-button"
                aria-label="关闭通知"
                onClick={() => setShowNotifications(false)}
              >
                <X size={17} />
              </button>
            </div>
            {!notifications.length && (
              <p className="muted-text">目前没有新通知。</p>
            )}
            {notifications.map((n) => (
              <button
                className={`notification ${n.read ? "" : "unread"}`}
                key={n.id}
                onClick={async () => {
                  try {
                    const resumed = await assistantApi.resume(n.id);
                    setNotifications((prev) =>
                      prev.map((x) =>
                        x.id === n.id ? { ...x, read: true } : x,
                      ),
                    );
                    setCurrent(resumed.conversation_id);
                    setPage("chat");
                    setShowNotifications(false);
                  } catch (e) {
                    setError(errorMessage(e));
                  }
                }}
              >
                <strong>{n.title}</strong>
                <span>{n.body.slice(0, 100)}</span>
                <small>{fmt(n.created_at)}</small>
              </button>
            ))}
          </div>
        )}
      </main>
      {deleteTarget && (
        <div
          className="modal-backdrop"
          onClick={(e) => {
            if (e.target === e.currentTarget && !deleting)
              setDeleteTarget(null);
          }}
        >
          <section
            className="modal delete-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-chat-title"
          >
            <h2 id="delete-chat-title">删除这段对话？</h2>
            <p>「{deleteTarget.title}」将从历史记录中移除。</p>
            <div className="modal-footer">
              <Button disabled={deleting} onClick={() => setDeleteTarget(null)}>
                取消
              </Button>
              <Button
                className="danger-button"
                disabled={deleting}
                onClick={async () => {
                  setDeleting(true);
                  try {
                    await accountApi.remove(deleteTarget.id);
                    messageCache.current.delete(deleteTarget.id);
                    setConversations((items) =>
                      items.filter((c) => c.id !== deleteTarget.id),
                    );
                    setHits((items) =>
                      items.filter(
                        (h) => h.conversation_id !== deleteTarget.id,
                      ),
                    );
                    if (current === deleteTarget.id) {
                      setCurrent("");
                      setMessages([]);
                      setPartial("");
                      setOptimistic(null);
                      setDraft("");
                      setAttachments([]);
                      setBusy(false);
                    }
                    setDeleteTarget(null);
                  } catch (e) {
                    setError(errorMessage(e));
                  } finally {
                    setDeleting(false);
                  }
                }}
              >
                {deleting ? "正在删除…" : "删除对话"}
              </Button>
            </div>
          </section>
        </div>
      )}
      {authOpen && (
        <div className="modal-backdrop">
          <div className="auth-dialog">
            <button
              className="icon-button auth-close"
              aria-label="关闭登录"
              onClick={() => setAuthOpen(false)}
            >
              <X size={18} />
            </button>
            <Login
              initialRegister={authRegister}
              onLogin={(name, isGuest = false, keep = false) => {
                if (!keep) {
                  setCurrent("");
                  setMessages([]);
                  setConversations([]);
                  history.replaceState({}, "", "/");
                }
                setUser(name);
                setGuest(isGuest);
                setAuthOpen(false);
              }}
            />
          </div>
        </div>
      )}
      {showSchedule && (
        <ScheduleModal
          conversations={conversations}
          current={current}
          onClose={() => setShowSchedule(false)}
          onCreate={async (body, key) => {
            await api.createSchedule(body, key);
            await refreshTasks();
            setShowSchedule(false);
          }}
        />
      )}
    </div>
  );
}
function Login({
  onLogin,
  onGuest,
  initialRegister = false,
}: {
  onLogin: (name: string, guest?: boolean, keep?: boolean) => void;
  onGuest?: () => Promise<void>;
  initialRegister?: boolean;
}) {
  const [register, setRegister] = useState(initialRegister);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <div className="login-page">
      <div className="login-art">
        <div className="brand">
          <div className="brand-icon">
            <Sparkles size={23} />
          </div>
          <strong>Adex</strong>
        </div>
        <div>
          <div className="eyebrow">A SPACE FOR YOUR IDEAS</div>
          <h1>
            想法有了去处，
            <br />
            事情有了安排。
          </h1>
          <p>
            与你对话，记住偏好，
            <br />
            在需要的时候，按时行动。
          </p>
        </div>
        <small>你的个人 AI 工作空间</small>
      </div>
      <form
        className="login-form"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            const r = await (register
              ? api.register({ username, password })
              : api.login({ username, password }));
            onLogin(r.username, r.is_guest, register);
          } catch (e) {
            setError(errorMessage(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        <Badge tone="green">PRIVATE WORKSPACE</Badge>
        <h2>{register ? "创建账户" : "欢迎回来"}</h2>
        <p>
          {register
            ? "注册后保留当前访客对话，并解锁任务与创作"
            : "登录你的 Adex 个人工作空间"}
        </p>
        <label>
          账户
          <input
            autoComplete="username"
            placeholder={
              register ? "3–32 位字母、数字、下划线或短横线" : "用户名"
            }
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </label>
        <label>
          密码
          <input
            type="password"
            autoComplete={register ? "new-password" : "current-password"}
            placeholder="密码"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error && (
          <div role="alert" className="form-error">
            {error}
          </div>
        )}
        <Button className="primary" type="submit" disabled={busy}>
          {busy ? "正在处理…" : register ? "注册并继续" : "进入工作空间"}
          <ArrowRight size={17} />
        </Button>
        <button
          type="button"
          className="text-button auth-switch"
          onClick={() => {
            setRegister(!register);
            setError("");
          }}
        >
          {register ? "已有账户？登录" : "还没有账户？注册"}
        </button>
        {onGuest && (
          <Button
            type="button"
            onClick={() => onGuest().catch((e) => setError(errorMessage(e)))}
          >
            继续免登录使用
          </Button>
        )}
        <small>对话、文件与偏好保存在你的个人工作空间</small>
      </form>
    </div>
  );
}
function Empty({
  icon,
  title,
  text,
}: {
  icon: React.ReactNode;
  title: string;
  text: string;
}) {
  return (
    <div className="empty">
      <div>{icon}</div>
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}
function MemoryPage({
  memories,
  onAdd,
  onDelete,
  onCorrect,
}: {
  memories: Memory[];
  onAdd: (s: string) => Promise<void>;
  onDelete: (s: string) => Promise<void>;
  onCorrect: (id: string, s: string) => Promise<void>;
}) {
  const [content, setContent] = useState("");
  const [editing, setEditing] = useState("");
  const [edit, setEdit] = useState("");
  return (
    <div className="content-page">
      <div className="page-heading">
        <div>
          <p>保存明确的偏好。你始终可以纠正或删除它们。</p>
        </div>

      </div>
      <div className="memory-info">
        <ShieldCheck size={20} />
        <div>
          <strong>记忆由你掌控</strong>
          <p>
            这些偏好可用于新对话。删除后会清除派生上下文，阻止旧内容再次成为记忆。
          </p>
        </div>
      </div>
      <form
        className="add-memory"
        onSubmit={async (e) => {
          e.preventDefault();
          if (content.trim()) {
            await onAdd(content.trim());
            setContent("");
          }
        }}
      >
        <input
          aria-label="新增记忆"
          placeholder="例如：我喜欢简洁的中文回答"
          value={content}
          maxLength={2000}
          onChange={(e) => setContent(e.target.value)}
        />
        <Button type="submit" disabled={!content.trim()}>
          <Plus size={16} />
          记住
        </Button>
      </form>
      <div className="list-heading">
        <h2>
          长期记忆 <span className="count">{memories.length}</span>
        </h2>
        <span>也可以在聊天中说“记住：…”</span>
      </div>
      {!memories.length ? (
        <Empty
          icon={<Brain size={28} />}
          title="从一个偏好开始"
          text="你选择记住的内容，会在未来的对话中派上用场。"
        />
      ) : (
        <div className="memory-grid">
          {memories.map((m) => (
            <div className="memory-card" key={m.id}>
              <div className="memory-card-top">
                <Badge>你确认的记忆</Badge>
                <div>
                  <button
                    className="icon-button"
                    aria-label="纠正记忆"
                    onClick={() => {
                      setEditing(m.id);
                      setEdit(m.content);
                    }}
                  >
                    <Pencil size={15} />
                  </button>
                  <button
                    className="icon-button"
                    aria-label="删除记忆"
                    onClick={() => onDelete(m.id)}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
              {editing === m.id ? (
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    await onCorrect(m.id, edit);
                    setEditing("");
                  }}
                >
                  <textarea
                    aria-label="纠正内容"
                    value={edit}
                    onChange={(e) => setEdit(e.target.value)}
                    maxLength={2000}
                  />
                  <Button type="submit">保存更正</Button>
                </form>
              ) : (
                <p>{m.content}</p>
              )}
              <small>跨会话可用 · 版本 {m.revision}</small>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
function ScheduleModal({
  conversations,
  current,
  onClose,
  onCreate,
}: {
  conversations: Conversation[];
  current: string;
  onClose: () => void;
  onCreate: (
    b: components["schemas"]["ScheduleInput"],
    key: string,
  ) => Promise<void>;
}) {
  const [title, setTitle] = useState("");
  const [instruction, setInstruction] = useState("");
  const [kind, setKind] = useState<"ONCE" | "DAILY" | "INTERVAL">("DAILY");
  const [timezone, setTimezone] = useState("Asia/Shanghai");
  const [time, setTime] = useState("08:00");
  const [when, setWhen] = useState("");
  const [interval, setInterval] = useState(60);
  const [conv, setConv] = useState(current || conversations[0]?.id || "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [natural, setNatural] = useState("");
  const [draftFire, setDraftFire] = useState("");
  const parseRequest = useRef<{ text: string; id: string } | null>(null);
  const submission = useRef<{ hash: string; key: string } | null>(null);
  return (
    <div className="modal-backdrop">
      <form
        className="modal"
        onSubmit={async (e) => {
          e.preventDefault();
          if (busy) return;
          setBusy(true);
          setError("");
          try {
            const body: components["schemas"]["ScheduleInput"] = {
              title,
              instruction,
              kind,
              timezone,
              origin_conversation_id: conv,
              first_fire_at:
                kind === "ONCE"
                  ? new Date(when).toISOString()
                  : draftFire || new Date(Date.now() + 5000).toISOString(),
              ...(kind === "DAILY" ? { local_time: time } : {}),
              ...(kind === "INTERVAL"
                ? { interval_seconds: interval * 60 }
                : {}),
            };
            // Preserve both request payload and idempotency key across ambiguous network failures.
            const hash = JSON.stringify({
              ...body,
              first_fire_at: kind === "ONCE" ? body.first_fire_at : "",
            });
            if (submission.current?.hash !== hash)
              submission.current = { hash, key: crypto.randomUUID() };
            const key = submission.current.key;
            const stored = sessionStorage.getItem("adex-schedule:" + key);
            const payload = stored ? JSON.parse(stored) : body;
            sessionStorage.setItem(
              "adex-schedule:" + key,
              JSON.stringify(payload),
            );
            await onCreate(payload, key);
            sessionStorage.removeItem("adex-schedule:" + key);
          } catch (e) {
            setError(errorMessage(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="modal-heading">
          <div>
            <div className="eyebrow">PLAN SOMETHING AHEAD</div>
            <h2>新建定时任务</h2>
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="关闭"
            onClick={onClose}
          >
            <X size={19} />
          </button>
        </div>
        <div className="natural-draft">
          <label>
            用一句话安排
            <input
              value={natural}
              onChange={(e) => setNatural(e.target.value)}
              placeholder="例如：每天早上八点提醒我整理今日重点"
              maxLength={2000}
            />
          </label>
          <Button
            type="button"
            disabled={busy || !natural.trim() || !conv}
            onClick={async () => {
              setBusy(true);
              setError("");
              try {
                if (parseRequest.current?.text !== natural)
                  parseRequest.current = {
                    text: natural,
                    id: crypto.randomUUID(),
                  };
                const d = await api.scheduleDraft({
                  request_id: parseRequest.current.id,
                  origin_conversation_id: conv,
                  instruction: natural,
                  timezone,
                });
                if (d.clarification) {
                  setError(d.clarification);
                  return;
                }
                setTitle(d.title || "");
                setInstruction(d.instruction || "");
                setKind(d.kind || "DAILY");
                setTimezone(d.timezone || timezone);
                setTime(d.local_time || "08:00");
                setInterval((d.interval_seconds || 3600) / 60);
                setDraftFire(d.first_fire_at || "");
                if (d.first_fire_at) {
                  const date = new Date(d.first_fire_at);
                  setWhen(
                    new Date(date.getTime() - date.getTimezoneOffset() * 60000)
                      .toISOString()
                      .slice(0, 16),
                  );
                }
              } catch (e) {
                setError(errorMessage(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            <Sparkles size={14} />
            {busy ? "正在解析…" : "生成草稿"}
          </Button>
          <small>检查下方时间与内容，确认后才会创建任务。</small>
        </div>
        <label>
          任务名称
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={200}
            placeholder="例如：每日早间简报"
            required
          />
        </label>
        <label>
          让 Adex 做什么
          <textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            maxLength={16000}
            rows={3}
            placeholder="说明执行内容；需要最新信息时请写明搜索范围"
            required
          />
        </label>
        <div className="form-row">
          <label>
            执行频率
            <select
              value={kind}
              onChange={(e) => setKind(e.target.value as typeof kind)}
            >
              <option value="DAILY">每天</option>
              <option value="ONCE">一次性</option>
              <option value="INTERVAL">固定间隔</option>
            </select>
          </label>
          <label>
            时区
            <select
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
            >
              <option>Asia/Shanghai</option>
              <option>Asia/Tokyo</option>
              <option>Europe/London</option>
              <option>America/New_York</option>
              <option>UTC</option>
            </select>
          </label>
        </div>
        {kind === "DAILY" ? (
          <label>
            每天的执行时间（{timezone}）
            <input
              type="time"
              value={time}
              onChange={(e) => setTime(e.target.value)}
              required
            />
          </label>
        ) : kind === "ONCE" ? (
          <label>
            执行时间（设备时区{" "}
            {Intl.DateTimeFormat().resolvedOptions().timeZone}）
            <input
              type="datetime-local"
              value={when}
              onChange={(e) => setWhen(e.target.value)}
              required
            />
          </label>
        ) : (
          <label>
            间隔（分钟，至少 1 分钟）
            <input
              type="number"
              min={1}
              max={525600}
              value={interval}
              onChange={(e) => setInterval(Number(e.target.value))}
              required
            />
          </label>
        )}
        <label>
          将结果发送到
          <select
            value={conv}
            onChange={(e) => setConv(e.target.value)}
            required
          >
            <option value="" disabled>
              选择原会话
            </option>
            {conversations.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))}
          </select>
        </label>
        {!conversations.length && (
          <div className="form-error">
            请先创建一个对话，作为任务结果的接收位置。
          </div>
        )}
        <div className="modal-note">
          <Clock3 size={15} />
          关闭页面后继续执行，结果保存到原对话。
        </div>
        {error && (
          <div className="form-error" role="alert">
            {error}
          </div>
        )}
        <div className="modal-footer">
          <Button type="button" onClick={onClose}>
            取消
          </Button>
          <Button className="primary" type="submit" disabled={busy || !conv}>
            {busy ? "正在创建…" : "确认创建"}
            <Check size={16} />
          </Button>
        </div>
      </form>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
