import { useEffect, useRef, useState } from "react";
import {
  Globe2,
  MousePointer2,
  Play,
  RefreshCw,
  LockKeyhole,
  X,
} from "lucide-react";
import { api, type Conversation } from "./api";
import { assistantApi, type Action } from "./assistantApi";
import {
  browserApi,
  type BrowserSession,
  type BrowserView,
} from "./browserApi";
import "./browser.css";
const labels: Record<string, string> = {
  AGENT: "Adex 操作中",
  HUMAN: "由你接管",
  WAITING_APPROVAL: "等待确认",
  UNKNOWN: "结果待核实",
  CLOSED: "已关闭",
  LOST: "会话待恢复",
};
export function BrowserPanel({
  conversation,
  onConversationCreated,
}: {
  conversation: string;
  onConversationCreated: (c: Conversation) => void;
}) {
  const [sessions, setSessions] = useState<BrowserSession[]>([]),
    [selected, setSelected] = useState(""),
    [view, setView] = useState<BrowserView | null>(null),
    [actions, setActions] = useState<Action[]>([]);
  const [url, setUrl] = useState(""),
    [goal, setGoal] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [field, setField] = useState(""),
    [secure, setSecure] = useState("");
  const pending = useRef(false),
    current = useRef(""),
    epoch = useRef(0),
    startKey = useRef(crypto.randomUUID());
  const [accounts, setAccounts] = useState<
    { id: string; host: string; expires_at: string }[]
  >([]);
  const [zoom, setZoom] = useState(false);
  const human = view?.status === "HUMAN";
  async function refresh() {
    const generation = epoch.current;
    const [list, approval] = await Promise.all([
      browserApi.list(),
      assistantApi.actions(),
    ]);
    if (generation !== epoch.current) return;
    setSessions(list.items);
    const saved = await browserApi.accounts();
    if (generation === epoch.current) setAccounts(saved.items);
    setActions(approval.items.filter((a) => a.kind === "browser.request"));
    if (current.current) {
      const value = await browserApi.view(current.current);
      if (generation === epoch.current && value.id === current.current)
        setView(value);
    }
    if (list.availability === "BLOCKED_EXTERNAL")
      setError("浏览器凭据加密尚未配置，请联系管理员。");
  }
  useEffect(() => {
    let live = true;
    const update = () => {
      if (live && !pending.current) void refresh().catch(() => {});
    };
    update();
    const timer = setInterval(update, 3000);
    const clear = () => {
      epoch.current++;
      current.current = "";
      setSelected("");
      setView(null);
      setSessions([]);
      setActions([]);
      setAccounts([]);
      setSecure("");
    };
    window.addEventListener("adex:session-changed", clear);
    return () => {
      live = false;
      epoch.current++;
      clearInterval(timer);
      window.removeEventListener("adex:session-changed", clear);
    };
  }, []);
  async function act(work: () => Promise<unknown>) {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      await work();
      await refresh();
    } catch (e) {
      setError("操作未完成：" + String(e instanceof Error ? e.message : e));
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }
  const action = actions.find((a) => a.id === view?.action_id);
  const fields =
    view?.nodes?.filter(
      (n) => n.id && ["textbox", "searchbox", "combobox"].includes(n.role),
    ) ?? [];
  async function control(body: Record<string, unknown>) {
    if (!selected) return;
    setView(await browserApi.control(selected, body));
  }
  return (
    <div className="browser-panel">
      <div className="browser-intro">
        <Globe2 size={22} />
        <div>
          <strong>让 Adex 在网页上办事</strong>
          <p>准备、登录接管、审核、执行；需要确认时暂停，结果回到原会话。</p>
        </div>
        <button
          aria-label="刷新浏览器任务"
          disabled={busy}
          onClick={() => void act(refresh)}
        >
          <RefreshCw size={17} />
        </button>
      </div>
      {error && (
        <p role="alert" className="experience-inline-error">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      <form
        className="browser-create"
        onSubmit={(e) => {
          e.preventDefault();
          void act(async () => {
            let conv = conversation;
            if (!conv) {
              const c = await api.createConversation("网页操作");
              onConversationCreated(c);
              conv = c.id;
            }
            await browserApi.start(conv, url, goal, startKey.current);
            startKey.current = crypto.randomUUID();
            setNotice("网页任务已进入后台执行，需要登录或确认时会暂停。");
          });
        }}
      >
        <input
          aria-label="网页地址"
          type="url"
          placeholder="https://…（公开网站）"
          value={url}
          required
          onChange={(e) => {
            setUrl(e.target.value);
            startKey.current = crypto.randomUUID();
          }}
        />
        <textarea
          aria-label="网页任务目标"
          placeholder="描述要准备的内容或要寻找的商品、规格和预算；不要在这里填写密码。"
          value={goal}
          required
          maxLength={16000}
          onChange={(e) => {
            setGoal(e.target.value);
            startKey.current = crypto.randomUUID();
          }}
        />
        <button className="button" disabled={busy || !goal || !url}>
          开始网页任务
        </button>
      </form>
      {!!accounts.length && (
        <div className="browser-accounts">
          <strong>已保存的站点会话</strong>
          {accounts.map((account) => (
            <div key={account.id}>
              <span>
                {account.host} · 有效至{" "}
                {new Date(account.expires_at).toLocaleDateString()}
              </span>
              <button
                disabled={busy}
                onClick={() => {
                  if (window.confirm("撤销本站登录并关闭相关网页任务？"))
                    void act(() => browserApi.revokeAccount(account.id));
                }}
              >
                撤销登录
              </button>
            </div>
          ))}
        </div>
      )}
      <div className="browser-sessions">
        {sessions.map((s) => (
          <button
            key={s.id}
            aria-pressed={selected === s.id}
            onClick={() => {
              current.current = s.id;
              setSelected(s.id);
              setView(null);
              setSecure("");
              void act(refresh);
            }}
          >
            <span>{s.current_url || "网页任务"}</span>
            <small>{labels[s.status] || s.status}</small>
          </button>
        ))}
      </div>
      {view && (
        <section className="browser-view">
          <header>
            <div>
              <strong>{view.title || "浏览器"}</strong>
              <small>{view.url || view.current_url}</small>
              <span>{labels[view.status] || view.status}</span>
            </div>
            <button
              aria-label="关闭浏览器并清除登录状态"
              disabled={busy}
              onClick={() => {
                if (
                  window.confirm(
                    "关闭此网页任务并清除本任务的登录状态？主动保存的站点账号可另行撤销。未确认的请求将撤销。",
                  )
                )
                  void act(async () => {
                    await browserApi.close(selected);
                    setView(null);
                    current.current = "";
                    setSelected("");
                  });
              }}
            >
              <X size={18} />
            </button>
          </header>
          <div className="browser-controls">
            <button
              disabled={busy || view.status !== "AGENT"}
              onClick={() => void act(() => control({ action: "takeover" }))}
            >
              <MousePointer2 size={16} />
              接管浏览器
            </button>
            <button
              disabled={
                busy ||
                view.run_status !== "WAITING_INPUT" ||
                !["AGENT", "HUMAN"].includes(view.status)
              }
              onClick={() =>
                void act(async () => {
                  await browserApi.resume(selected);
                  setSecure("");
                })
              }
            >
              <Play size={16} />
              {human ? "交还 Adex" : "继续任务"}
            </button>
            <button disabled={busy} onClick={() => setZoom((value) => !value)}>
              {zoom ? "适应屏幕" : "放大页面"}
            </button>
            <button
              disabled={busy || view.status === "CLOSED"}
              onClick={() => {
                if (
                  window.confirm(
                    "恢复会重新打开当前页面并交由你接管。未发送的审批将撤销，页面中未保存的草稿可能丢失。继续？",
                  )
                )
                  void act(() => control({ action: "recover" }));
              }}
            >
              恢复并接管
            </button>
            <button
              disabled={busy || view.status === "CLOSED"}
              onClick={() => {
                if (
                  window.confirm(
                    "加密保存当前站点的登录状态7天，用于后续网页任务？不保存输入过的密码，可随时撤销。",
                  )
                )
                  void act(() =>
                    control({
                      action: "remember",
                      profile_revision: view.profile_revision ?? 0,
                    }),
                  );
              }}
            >
              记住本站登录
            </button>
          </div>
          {!!view.tabs?.length && (
            <select
              aria-label="浏览器标签页"
              disabled={busy || !human}
              value={view.tabs.find((tab) => tab.active)?.id ?? ""}
              onChange={(event) =>
                void act(() =>
                  control({
                    action: "switch_tab",
                    element_id: event.target.value,
                  }),
                )
              }
            >
              {view.tabs.map((tab) => (
                <option key={tab.id} value={tab.id}>
                  {tab.url || "新标签页"}
                </option>
              ))}
            </select>
          )}
          {view.dialog && (
            <div className="browser-approval">
              <strong>网页确认窗口</strong>
              <small>{view.dialog.url}</small>
              <p>{view.dialog.message}</p>
              {human ? (
                <div className="browser-controls">
                  <button
                    disabled={busy}
                    onClick={() =>
                      void act(() =>
                        control({
                          action: "dialog_accept",
                          dialog_id: view.dialog?.id,
                        }),
                      )
                    }
                  >
                    确认网页提示
                  </button>
                  <button
                    disabled={busy}
                    onClick={() =>
                      void act(() =>
                        control({
                          action: "dialog_dismiss",
                          dialog_id: view.dialog?.id,
                        }),
                      )
                    }
                  >
                    取消网页提示
                  </button>
                </div>
              ) : (
                <p>请先接管浏览器，再处理此提示。</p>
              )}
            </div>
          )}
          {view.screenshot ? (
            <div className={`browser-stage ${zoom ? "zoomed" : ""}`}>
              <img
                className={human ? "human" : ""}
                src={"data:image/jpeg;base64," + view.screenshot}
                alt="当前远程浏览器页面；接管后可点击操作"
                draggable={false}
                onClick={(e) => {
                  if (!human || busy) return;
                  const rect = e.currentTarget.getBoundingClientRect();
                  void act(() =>
                    control({
                      action: "point",
                      x: Math.min(
                        1099,
                        Math.floor(
                          ((e.clientX - rect.left) / rect.width) * 1100,
                        ),
                      ),
                      y: Math.min(
                        779,
                        Math.floor(
                          ((e.clientY - rect.top) / rect.height) * 780,
                        ),
                      ),
                    }),
                  );
                }}
              />
            </div>
          ) : (
            <p>页面预览正在准备，稍后会自动更新。</p>
          )}
          {human && (
            <div className="browser-secure">
              <p>
                <LockKeyhole size={15} /> 现在由你操作，Adex
                已暂停。输入只发送给当前浏览器，不进入聊天或模型。
              </p>
              <select
                aria-label="选择网页输入框"
                value={field}
                onChange={(e) => setField(e.target.value)}
              >
                <option value="">页面中当前选中的输入框（先点击页面）</option>
                {fields.map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.name || "未命名输入框"}
                    {n.protected ? "（安全输入）" : ""}
                  </option>
                ))}
              </select>
              <input
                aria-label="安全输入内容"
                type="password"
                autoComplete="off"
                value={secure}
                placeholder="账号、密码或验证码"
                onChange={(e) => setSecure(e.target.value)}
              />
              <button
                disabled={busy || !secure}
                onClick={() => {
                  const value = secure;
                  setSecure("");
                  void act(() =>
                    control({ action: "type", element_id: field, text: value }),
                  );
                }}
              >
                输入到网页
              </button>
              <div className="browser-controls">
                {["Enter", "Tab", "Backspace"].map((key) => (
                  <button
                    key={key}
                    disabled={busy}
                    onClick={() =>
                      void act(() => control({ action: "key", text: key }))
                    }
                  >
                    {key}
                  </button>
                ))}
                <button
                  disabled={busy}
                  onClick={() =>
                    void act(() => control({ action: "scroll", text: "up" }))
                  }
                >
                  向上滚动
                </button>
                <button
                  disabled={busy}
                  onClick={() =>
                    void act(() => control({ action: "scroll", text: "down" }))
                  }
                >
                  向下滚动
                </button>
              </div>
            </div>
          )}
          {action && (
            <div className="browser-approval">
              <strong>
                {action.state === "UNKNOWN"
                  ? "执行结果待核实"
                  : "请核对本次网页请求"}
              </strong>
              <p>
                确认仅授权下列具体请求。请求已送达不等于发布成功、订单成立或付款完成。
              </p>
              {action.request.summary && (
                <div className="browser-review">
                  <strong>{action.request.summary.kind}</strong>
                  <small>{action.request.summary.page_url}</small>
                  {action.request.summary.fields.map((field, index) => (
                    <div key={index}>
                      <b>{field.label}</b>
                      <p>{field.value}</p>
                    </div>
                  ))}
                  {action.request.summary.facts.map((fact, index) => (
                    <p key={index}>{fact}</p>
                  ))}
                </div>
              )}
              {action.request.payload.reviewable === false &&
                !action.request.payload.additional_permission && (
                  <p>
                    该请求内容无法完整解析，请选择“不提交，交给我处理”，在网页中亲自操作。
                  </p>
                )}
              <details>
                <summary>请求核对信息</summary>
                <pre>{JSON.stringify(action.request.payload, null, 2)}</pre>
              </details>
              {["PENDING", "APPROVED"].includes(action.state) && (
                <div className="browser-controls">
                  <button
                    disabled={busy || (action.request.payload.reviewable === false && !action.request.payload.additional_permission)}
                    onClick={() =>
                      void act(() => assistantApi.decide(action, "approve"))
                    }
                  >
                    确认并继续
                  </button>
                  <button
                    disabled={busy}
                    onClick={() =>
                      void act(() => assistantApi.decide(action, "revoke"))
                    }
                  >
                    不提交，交给我处理
                  </button>
                </div>
              )}
              {action.state === "UNKNOWN" && (
                <button
                  disabled={busy}
                  onClick={() =>
                    void act(() => assistantApi.decide(action, "reconcile"))
                  }
                >
                  核对结果（不会重复提交）
                </button>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
