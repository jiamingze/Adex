import { useEffect, useRef, useState } from "react";
import {
  Globe2,
  LockKeyhole,
  LoaderCircle,
  CheckCircle2,
  ExternalLink,
  RefreshCw,
} from "lucide-react";
import { browserApi, type BrowserRun } from "./browserApi";
import { assistantApi } from "./assistantApi";
import "./browserChat.css";

const statusLabels: Record<string, string> = {
  QUEUED: "正在准备",
  RUNNING: "Adex 正在处理",
  WAITING_INPUT: "需要你处理",
  COMPLETED: "处理完成",
  FAILED: "处理未完成",
  CANCELLED: "已取消",
};
const terminal = new Set(["COMPLETED", "FAILED", "CANCELLED", "SUCCEEDED"]);
function host(value: string) {
  try {
    return new URL(value).hostname;
  } catch {
    return "当前网站";
  }
}
function link(value: unknown) {
  try {
    const u = new URL(String(value));
    return u.protocol === "https:" && !u.username && !u.password ? u.href : "";
  } catch {
    return "";
  }
}

export function BrowserTaskCard({
  runId,
  conversationId,
}: {
  runId: string;
  conversationId: string;
}) {
  const [data, setData] = useState<BrowserRun | null>(null),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [values, setValues] = useState<Record<string, string>>({}),
    [remember, setRemember] = useState(false),
    [submitId, setSubmitId] = useState(""),
    [manual, setManual] = useState(""),
    [zoom, setZoom] = useState(false);
  const root = useRef<HTMLElement>(null),
    live = useRef(true),
    pending = useRef(false),
    inView = useRef(true),
    generation = useRef(0);
  async function refresh() {
    const token = generation.current;
    const next = await browserApi.run(runId);
    if (!live.current || token !== generation.current) return;
    if (next.run_id !== runId || next.conversation_id !== conversationId)
      throw Error("网页任务与当前会话不匹配");
    setData(next);
    setError("");
    return next;
  }
  useEffect(() => {
    live.current = true;
    let timer: ReturnType<typeof setTimeout>;
    const observer = new IntersectionObserver((entries) => {
      inView.current = entries.some((e) => e.isIntersecting);
    });
    if (root.current) observer.observe(root.current);
    const tick = async () => {
      let next: BrowserRun | undefined;
      try {
        if (
          !pending.current &&
          document.visibilityState !== "hidden" &&
          inView.current
        )
          next = await refresh();
      } catch {
        if (live.current) setError("状态暂时无法同步，请刷新重试。");
      }
      if (live.current && !terminal.has(next?.status || ""))
        timer = setTimeout(tick, 2500);
    };
    void tick();
    const clear = () => {
      generation.current++;
      setValues({});
      setManual("");
      setRemember(false);
      setData(null);
    };
    window.addEventListener("adex:session-changed", clear);
    return () => {
      live.current = false;
      generation.current++;
      clearTimeout(timer);
      observer.disconnect();
      window.removeEventListener("adex:session-changed", clear);
    };
  }, [runId, conversationId]);
  const view = data?.session,
    action = data?.action,
    form = view?.login_form,
    human = view?.status === "HUMAN",
    waiting = data?.status === "WAITING_INPUT";
  const signature = form
    ? form.origin + form.fields.map((f) => f.id).join(",")
    : "";
  useEffect(() => {
    setValues({});
    setSubmitId(form?.buttons[0]?.id || "");
  }, [signature]);
  async function act(work: () => Promise<unknown>) {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      await work();
      await refresh();
    } catch (e) {
      if (live.current)
        setError(e instanceof Error ? e.message : "操作未完成，请重试。");
    } finally {
      pending.current = false;
      if (live.current) setBusy(false);
    }
  }
  const receipts =
    view?.business_receipts || data?.result?.artifact?.receipts || [];
  const receipt = [...receipts]
    .reverse()
    .find((r) => r.business_verified === true);
  const summary = action?.request.summary;
  const draftFields = summary?.fields.filter(
    (f) =>
      !["可编辑区域", "输入内容"].includes(f.label) ||
      !summary.fields.some(
        (other) =>
          other !== f &&
          !["可编辑区域", "输入内容"].includes(other.label) &&
          other.value === f.value,
      ),
  );
  const canApprove =
    waiting &&
    ["PENDING", "APPROVED"].includes(action?.state || "") &&
    !(
      action?.request.payload.reviewable === false &&
      !action?.request.payload.additional_permission
    );
  async function continueTask() {
    if (!view) return;
    if (remember)
      await browserApi.control(view.id, {
        action: "remember",
        profile_revision: view.profile_revision || 0,
      });
    await browserApi.resume(view.id);
    setNotice("已交还 Adex，将继续处理原任务。");
  }
  return (
    <section
      className="browser-chat-card"
      ref={root}
      aria-label="会话内网页任务"
    >
      <header>
        <Globe2 size={19} />
        <div>
          <strong>网页助手</strong>
          <small>
            {view?.url || view?.current_url || "任务将在当前会话持续更新"}
          </small>
        </div>
        <span className="browser-chat-status">
          {busy ? <LoaderCircle size={14} className="spin" /> : null}
          {statusLabels[data?.status || "QUEUED"] || data?.status}
        </span>
      </header>
      {error && (
        <p role="alert" className="browser-chat-error">
          {error}
          <button aria-label="刷新网页任务" onClick={() => void act(refresh)}>
            <RefreshCw size={14} />
          </button>
        </p>
      )}
      {notice && !action && !terminal.has(data?.status || "") && (
        <p className="browser-chat-notice" role="status">
          {notice}
        </p>
      )}
      {view?.progress_events?.length ? (
        <details className="browser-chat-progress">
          <summary>
            {view.progress_events.at(-1)?.text} ·{" "}
            {view.progress_events.at(-1)?.step} 步
          </summary>
          <ol>
            {view.progress_events.map((p, i) => (
              <li key={i}>{p.text}</li>
            ))}
          </ol>
        </details>
      ) : !terminal.has(data?.status || "") && !human && !action ? (
        <p className="browser-chat-muted">正在打开网站、检查页面并准备内容…</p>
      ) : null}
      {human && form && (
        <form
          className="browser-chat-login"
          onSubmit={(event) => {
            event.preventDefault();
            const submitted = Object.entries(values)
              .filter(([, text]) => text)
              .map(([element_id, text]) => ({ element_id, text }));
            void act(async () => {
              try {
                const result = (await browserApi.control(view.id, {
                  action: "secure_login",
                  origin: form.origin,
                  observation_id: form.observation_id,
                  submit_element_id: submitId,
                  fields: submitted,
                  remember_login: remember,
                  profile_revision: view.profile_revision || 0,
                })) as typeof view & {
                  auto_resumed?: boolean;
                  remembered?: boolean;
                };
                setNotice(
                  result.auto_resumed
                    ? `登录请求已提交，Adex 正在继续${result.remembered ? "；会话状态已加密保存" : ""}。`
                    : "登录请求已提交，请继续处理网站要求的验证。此提示不代表已经登录成功。",
                );
              } finally {
                setValues({});
              }
            });
          }}
        >
          <div className="browser-chat-login-title">
            <LockKeyhole size={17} />
            <div>
              <strong>安全登录到 {host(form.origin)}</strong>
              <small>
                Adex 转交网站的真实输入框，凭据不发送给模型或写入聊天。
              </small>
            </div>
          </div>
          {form.fields.map((field) => (
            <label key={field.id}>
              {field.label}
              <input
                name={`site-field-${field.id}`}
                type={
                  field.secret
                    ? "password"
                    : field.type === "email"
                      ? "email"
                      : "text"
                }
                inputMode={
                  /手机|电话|验证码|phone|otp/i.test(field.label)
                    ? "numeric"
                    : "text"
                }
                autoComplete="off"
                value={values[field.id] || ""}
                disabled={busy || !waiting}
                onChange={(e) =>
                  setValues((v) => ({ ...v, [field.id]: e.target.value }))
                }
              />
            </label>
          ))}
          {form.buttons.length > 1 && (
            <label>
              网站操作
              <select
                aria-label="选择登录操作"
                value={submitId}
                onChange={(e) => setSubmitId(e.target.value)}
              >
                {form.buttons.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.label}
                  </option>
                ))}
              </select>
            </label>
          )}
          {form.notices.map((n, i) => (
            <small key={i}>{n}</small>
          ))}
          <label className="browser-chat-remember">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
            />
            记住本站登录状态 7 天（不保存输入密码）
          </label>
          <button
            className="browser-chat-primary"
            disabled={busy || !waiting || !Object.values(values).some(Boolean)}
            type="submit"
          >
            {busy
              ? "正在提交…"
              : `${form.buttons.find((b) => b.id === submitId)?.label || "登录"}并继续`}
          </button>
          {!waiting && <small>正在安全暂停网页任务，稍后即可操作。</small>}
        </form>
      )}
      {action && (
        <div className="browser-chat-approval">
          <strong>{summary?.kind || "请核对待提交的网页操作"}</strong>
          <small>
            提交目标：
            {host(
              String(
                action.request.payload.destination || summary?.page_url || "",
              ),
            )}
          </small>
          <p>请核对下面的标题、正文与网站，确认后才会提交。</p>
          {draftFields?.map((f, i) => (
            <div className="browser-chat-draft" key={i}>
              <small>{f.label}</small>
              <pre>{f.value}</pre>
            </div>
          ))}
          {summary?.facts.map((f, i) => (
            <p key={i}>{f}</p>
          ))}
          <details>
            <summary>目标与请求详情</summary>
            <pre>{JSON.stringify(action.request.payload, null, 2)}</pre>
          </details>
          {action.state === "UNKNOWN" ? (
            <>
              <p>请求结果尚未核实，不会自动重复发表。</p>
              <button
                disabled={busy}
                onClick={() =>
                  void act(() => assistantApi.decide(action, "reconcile"))
                }
              >
                核对结果
              </button>
            </>
          ) : (
            <div className="browser-chat-actions">
              <button
                className="browser-chat-primary"
                disabled={busy || !canApprove}
                onClick={() =>
                  void act(() => assistantApi.decide(action, "approve"))
                }
              >
                {summary?.kind === "发布内容" ? "确认发表" : "确认并继续"}
              </button>
              <button
                disabled={
                  busy ||
                  !waiting ||
                  !["PENDING", "APPROVED"].includes(action.state)
                }
                onClick={() =>
                  void act(() => assistantApi.decide(action, "revoke"))
                }
              >
                暂不提交，交给我
              </button>
            </div>
          )}
        </div>
      )}
      {view?.dialog && (
        <div className="browser-chat-approval">
          <strong>网站确认窗口</strong>
          <p>{view.dialog.message}</p>
          <div className="browser-chat-actions">
            <button
              disabled={busy || !human}
              onClick={() =>
                void act(() =>
                  browserApi.control(view.id, {
                    action: "dialog_accept",
                    dialog_id: view.dialog?.id,
                  }),
                )
              }
            >
              确认网站提示
            </button>
            <button
              disabled={busy || !human}
              onClick={() =>
                void act(() =>
                  browserApi.control(view.id, {
                    action: "dialog_dismiss",
                    dialog_id: view.dialog?.id,
                  }),
                )
              }
            >
              取消
            </button>
          </div>
        </div>
      )}
      {view && (
        <details className="browser-chat-page" open={human && !form}>
          <summary>
            {human ? "网站页面 · 扫码、验证码或手动操作" : "查看网站当前页面"}
          </summary>
          <button type="button" onClick={() => setZoom((v) => !v)}>
            {zoom ? "适应屏幕" : "放大网站页面"}
          </button>
          <div className="browser-chat-page-frame">
            {view.screenshot ? (
              <img
                style={{
                  width: zoom ? 1100 : "100%",
                  maxWidth: zoom ? "none" : "100%",
                }}
                src={`data:image/jpeg;base64,${view.screenshot}`}
                alt="当前真实网站页面，接管后可点击"
                onClick={(event) => {
                  if (!human || busy) return;
                  const box = event.currentTarget.getBoundingClientRect();
                  void act(() =>
                    browserApi.control(view.id, {
                      action: "point",
                      x: Math.min(
                        1099,
                        Math.max(
                          0,
                          Math.round(
                            ((event.clientX - box.left) * 1100) / box.width,
                          ),
                        ),
                      ),
                      y: Math.min(
                        779,
                        Math.max(
                          0,
                          Math.round(
                            ((event.clientY - box.top) * 780) / box.height,
                          ),
                        ),
                      ),
                    }),
                  );
                }}
              />
            ) : (
              <p>正在同步网站页面…</p>
            )}
          </div>
          {human && (
            <>
              <label>
                输入到页面当前选中的输入框
                <input
                  type="password"
                  value={manual}
                  autoComplete="off"
                  onChange={(e) => setManual(e.target.value)}
                  placeholder="先点击页面中的实际输入框"
                />
              </label>
              <div className="browser-chat-actions">
                <button
                  disabled={busy || !manual}
                  onClick={() =>
                    void act(async () => {
                      try {
                        await browserApi.control(view.id, {
                          action: "type",
                          text: manual,
                        });
                      } finally {
                        setManual("");
                      }
                    })
                  }
                >
                  输入
                </button>
                {["Enter", "Tab"].map((key) => (
                  <button
                    key={key}
                    disabled={busy}
                    onClick={() =>
                      void act(() =>
                        browserApi.control(view.id, {
                          action: "key",
                          text: key,
                        }),
                      )
                    }
                  >
                    {key}
                  </button>
                ))}
                <button
                  disabled={busy}
                  onClick={() =>
                    void act(() =>
                      browserApi.control(view.id, {
                        action: "scroll",
                        text: "down",
                      }),
                    )
                  }
                >
                  向下滚动
                </button>
              </div>
            </>
          )}
        </details>
      )}
      {human && !form && (
        <div className="browser-chat-continue">
          <label className="browser-chat-remember">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
            />
            记住当前站点会话状态 7 天
          </label>
          <button
            className="browser-chat-primary"
            disabled={busy || !waiting}
            onClick={() => void act(continueTask)}
          >
            我已处理，继续 Adex 任务
          </button>
        </div>
      )}
      {view?.status === "LOST" && (
        <button
          disabled={busy}
          onClick={() =>
            void act(() => browserApi.control(view.id, { action: "recover" }))
          }
        >
          恢复页面并接管
        </button>
      )}
      {receipt && (
        <div className="browser-chat-receipt">
          <CheckCircle2 size={19} />
          <div>
            <strong>
              {receipt.test_fixture
                ? "本地测试回执（非真实发表）"
                : data?.status === "COMPLETED"
                  ? "操作已完成并取得核验回执"
                  : "已取得核验回执"}
            </strong>
            {Boolean(receipt.title) && <p>提交标题：{String(receipt.title)}</p>}
            {receipt.test_fixture && receipt.permalink ? (
              <small>演示链接：{String(receipt.permalink)}</small>
            ) : link(receipt.permalink) ? (
              <a
                href={link(receipt.permalink)}
                target="_blank"
                rel="noopener noreferrer"
              >
                查看结果 <ExternalLink size={13} />
              </a>
            ) : (
              <small>网站未返回可核验的文章链接。</small>
            )}
            {Boolean(receipt.permalink) &&
              !receipt.permalink_verified &&
              !receipt.test_fixture && (
                <small>平台返回的链接，尚未单独打开核验。</small>
              )}
            <small>回执：{String(receipt.provider_receipt)}</small>
          </div>
        </div>
      )}
    </section>
  );
}
