import { useEffect, useState } from "react";
import {
  assistantApi,
  type Connection,
  type Action,
  type Signal,
  type NotificationPreferences,
} from "./assistantApi";
import { native, requestPush } from "./platform";
export function AssistantHub({ conversation }: { conversation: string }) {
  const [connections, setConnections] = useState<Connection[]>([]),
    [actions, setActions] = useState<Action[]>([]),
    [signals, setSignals] = useState<Signal[]>([]),
    [availability, setAvailability] = useState(""),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [selected, setSelected] = useState(""),
    [query, setQuery] = useState<Record<string, unknown> | null>(null),
    [eventId, setEventId] = useState(""),
    [start, setStart] = useState(""),
    [end, setEnd] = useState(""),
    [targetStart, setTargetStart] = useState(""),
    [targetEnd, setTargetEnd] = useState(""),
    [recipient, setRecipient] = useState(""),
    [subject, setSubject] = useState(""),
    [text, setText] = useState(""),
    [prefs, setPrefs] = useState<NotificationPreferences | null>(null);
  async function refresh() {
    const [c, a, s, p] = await Promise.all([
      assistantApi.connections(),
      assistantApi.actions(),
      assistantApi.signals(),
      assistantApi.preferences(),
    ]);
    setConnections(c.items);
    setAvailability(c.availability);
    setActions(a.items);
    setSignals(s.items);
    setPrefs(p);
  }
  useEffect(() => {
    refresh().catch((e) => setError(String(e)));
  }, []);
  async function act(work: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await work();
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  const connection = connections.find((c) => c.id === selected);
  const events = (Array.isArray(query?.events) ? query!.events : []) as {
    id: string;
    summary?: string;
    start?: { dateTime?: string; date?: string };
    end?: { dateTime?: string; date?: string };
  }[];
  const mails = (Array.isArray(query?.messages) ? query!.messages : []) as {
    id: string;
    headers: { name: string; value: string }[];
  }[];
  function localTime(value?: string) {
    if (!value) return "";
    const date = new Date(value);
    return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 16);
  }
  function chooseEvent(id: string) {
    setEventId(id);
    const event = events.find((e) => e.id === id);
    setTargetStart(localTime(event?.start?.dateTime));
    setTargetEnd(localTime(event?.end?.dateTime));
  }

  function interval(target = false) {
    const from = target ? targetStart : start,
      to = target ? targetEnd : end;
    if (!from || !to) throw new Error("请填写开始和结束时间");
    return {
      start: new Date(from).toISOString(),
      end: new Date(to).toISOString(),
    };
  }
  async function ensureConversation() {
    if (!conversation)
      throw new Error("请先打开或新建一个聊天，再将建议与操作关联到该会话");
    return conversation;
  }
  return (
    <div className="content-page assistant-hub">
      <div className="page-heading">
        <div>
          <h1>主动助手</h1>
          <p>连接日历与邮件，发现重要事项；对外操作始终由你确认。</p>
        </div>
        <button disabled={busy} onClick={() => act(refresh)}>
          刷新
        </button>
      </div>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      <section className="assistant-section">
        <h2>连接服务</h2>
        {availability === "BLOCKED_EXTERNAL" && (
          <p className="muted-text">
            BLOCKED_EXTERNAL：Google OAuth
            服务尚未配置，不能读取或修改真实账户。
          </p>
        )}
        {native && (
          <p className="muted-text">
            请先在 Web 端连接 Google 账户，授权完成后 iOS 可使用同一账户的连接。
          </p>
        )}
        <div className="assistant-actions">
          {[
            ["calendar", "read", "读取日历"],
            ["calendar", "write", "授权日历修改"],
            ["gmail", "read", "读取 Gmail"],
            ["gmail", "send", "授权发送邮件"],
          ].map(([service, access, label]) => (
            <button
              key={label}
              disabled={busy || native}
              onClick={() =>
                act(async () => {
                  const result = await assistantApi.authorize(service, access);
                  window.location.assign(result.authorization_url);
                })
              }
            >
              {label}
            </button>
          ))}
        </div>
        {connections.map((c) => (
          <div className="assistant-connection" key={c.id}>
            <div>
              <strong>
                {c.service === "calendar" ? "Google Calendar" : "Gmail"}
              </strong>
              <small>
                {c.status} · {c.id.slice(0, 8)}
              </small>
              <details>
                <summary>授权范围</summary>
                {c.scopes.map((s) => (
                  <p className="scope-text" key={s}>
                    {s.replace("https://www.googleapis.com/auth/", "")}
                  </p>
                ))}
              </details>
            </div>
            <button
              disabled={busy || c.status === "REVOKED"}
              onClick={() =>
                act(async () => {
                  const r = await assistantApi.revokeConnection(c.id);
                  setNotice(
                    r.status === "REVOKED"
                      ? "已撤销连接"
                      : "本地访问已停用，远端撤销待重试",
                  );
                })
              }
            >
              撤销
            </button>
          </div>
        ))}
      </section>
      <section className="assistant-section">
        <h2>查询与操作草稿</h2>
        <select
          aria-label="选择连接"
          value={selected}
          onChange={(e) => {
            setSelected(e.target.value);
            setQuery(null);
          }}
        >
          <option value="">选择已授权连接</option>
          {connections
            .filter((c) => c.status === "ACTIVE")
            .map((c) => (
              <option key={c.id} value={c.id}>
                {c.service} · {c.id.slice(0, 8)}
              </option>
            ))}
        </select>
        {connection && (
          <>
            <div className="assistant-fields">
              {connection.service === "calendar" ? (
                <>
                  <label>
                    开始
                    <input
                      type="datetime-local"
                      value={start}
                      onChange={(e) => setStart(e.target.value)}
                    />
                  </label>
                  <label>
                    结束
                    <input
                      type="datetime-local"
                      value={end}
                      onChange={(e) => setEnd(e.target.value)}
                    />
                  </label>
                </>
              ) : (
                <p>仅查询最近收件箱元数据，不读取邮件正文。</p>
              )}
            </div>
            <div className="assistant-actions">
              <button
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    setQuery(
                      await assistantApi.query(
                        selected,
                        connection.service === "calendar"
                          ? interval()
                          : { query: "in:inbox" },
                      ),
                    );
                  })
                }
              >
                查询{connection.service === "calendar" ? "与检测冲突" : "邮件"}
              </button>
              <button
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    const run = await assistantApi.sync(
                      selected,
                      await ensureConversation(),
                      connection.service === "calendar"
                        ? interval()
                        : { query: "in:inbox" },
                    );
                    setNotice("检查任务已创建：" + run.id);
                  })
                }
              >
                检查变化并生成建议
              </button>
              <button
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    await assistantApi.watch(
                      selected,
                      await ensureConversation(),
                    );
                    setNotice(
                      "已启用每15分钟检查，可在定时任务页面暂停或取消。",
                    );
                  })
                }
              >
                开启持续检查
              </button>
            </div>
            {events.map((e) => (
              <article className="signal-card" key={e.id}>
                <strong>{e.summary || "未命名事件"}</strong>
                <p>
                  {e.start?.dateTime
                    ? new Date(e.start.dateTime).toLocaleString()
                    : e.start?.date}{" "}
                  —{" "}
                  {e.end?.dateTime
                    ? new Date(e.end.dateTime).toLocaleString()
                    : e.end?.date}
                </p>
                {e.start?.dateTime && (
                  <button onClick={() => chooseEvent(e.id)}>
                    调整这个事件
                  </button>
                )}
              </article>
            ))}
            {mails.map((m) => (
              <article className="signal-card" key={m.id}>
                <strong>
                  {m.headers.find((h) => h.name.toLowerCase() === "subject")
                    ?.value || "无主题"}
                </strong>
                <p>
                  {
                    m.headers.find((h) => h.name.toLowerCase() === "from")
                      ?.value
                  }
                </p>
              </article>
            ))}
            {Array.isArray(query?.conflicts) && query!.conflicts.length > 0 && (
              <p role="status">
                发现 {query!.conflicts.length}{" "}
                组时间冲突，请选择需要调整的事件。
              </p>
            )}
            {query && (
              <details>
                <summary>查询依据与服务回执</summary>
                <pre className="assistant-evidence">
                  {JSON.stringify(query, null, 2)}
                </pre>
              </details>
            )}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                act(async () => {
                  await assistantApi.draft({
                    connection_id: selected,
                    origin_conversation_id: await ensureConversation(),
                    kind:
                      connection.service === "calendar"
                        ? "calendar.update"
                        : "gmail.send",
                    payload:
                      connection.service === "calendar"
                        ? { event_id: eventId, ...interval(true) }
                        : { to: recipient, subject, text },
                  });
                  setNotice("已生成待确认草稿，尚未执行。");
                });
              }}
            >
              {connection.service === "calendar" ? (
                <div className="assistant-fields">
                  <label>
                    选择要调整的事件
                    <select
                      required
                      value={eventId}
                      onChange={(e) => chooseEvent(e.target.value)}
                    >
                      <option value="">先查询日历，再选择事件</option>
                      {events.map((e) => (
                        <option key={e.id} value={e.id}>
                          {e.summary || "未命名事件"}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    调整后的开始时间
                    <input
                      required
                      type="datetime-local"
                      value={targetStart}
                      onChange={(e) => setTargetStart(e.target.value)}
                    />
                  </label>
                  <label>
                    调整后的结束时间
                    <input
                      required
                      type="datetime-local"
                      value={targetEnd}
                      onChange={(e) => setTargetEnd(e.target.value)}
                    />
                  </label>
                </div>
              ) : (
                <div className="assistant-fields">
                  <label>
                    收件人
                    <input
                      type="email"
                      required
                      value={recipient}
                      onChange={(e) => setRecipient(e.target.value)}
                    />
                  </label>
                  <label>
                    主题
                    <input
                      required
                      value={subject}
                      onChange={(e) => setSubject(e.target.value)}
                    />
                  </label>
                  <label>
                    正文
                    <textarea
                      required
                      value={text}
                      onChange={(e) => setText(e.target.value)}
                    />
                  </label>
                </div>
              )}
              <button disabled={busy} type="submit">
                生成操作草稿
              </button>
            </form>
          </>
        )}
      </section>
      <section className="assistant-section">
        <h2>待确认操作</h2>
        {!actions.length && <p className="muted-text">没有操作草稿</p>}
        {actions.map((a) => (
          <article className="approval-card" key={a.id}>
            <strong>
              {a.kind === "calendar.update" ? "调整日历事件" : "发送邮件"} ·{" "}
              {{
                PENDING: "待确认",
                APPROVED: "已批准",
                SUCCEEDED: "已核实完成",
                UNKNOWN: "结果待核对",
                REVOKED: "已撤销",
              }[a.state] || a.state}
            </strong>
            <small>有效期：{new Date(a.expires_at).toLocaleString()}</small>
            <div className="action-summary">
              {a.kind === "calendar.update" ? (
                <p>
                  调整为{" "}
                  {new Date(String(a.request.payload.start)).toLocaleString()} —{" "}
                  {new Date(String(a.request.payload.end)).toLocaleString()}
                </p>
              ) : (
                <>
                  <p>收件人：{String(a.request.payload.to)}</p>
                  <strong>{String(a.request.payload.subject)}</strong>
                  <p className="action-message">
                    {String(a.request.payload.text)}
                  </p>
                </>
              )}
            </div>
            <details>
              <summary>完整确认内容与回执</summary>
              <pre className="assistant-evidence">
                {JSON.stringify(
                  {
                    before: a.request.before,
                    changes: a.request.payload,
                    receipt: a.result,
                  },
                  null,
                  2,
                )}
              </pre>
            </details>
            {["PENDING", "APPROVED"].includes(a.state) && (
              <div className="assistant-actions">
                <button
                  disabled={busy}
                  onClick={() => {
                    if (
                      window.confirm(
                        "确认按以上具体内容修改日历或发送邮件？此操作会访问外部账户。",
                      )
                    )
                      act(async () => {
                        await assistantApi.decide(a, "approve");
                        setNotice("已确认，操作进入现有后台任务执行链路。");
                      });
                  }}
                >
                  确认执行
                </button>
                <button
                  disabled={busy}
                  onClick={() =>
                    act(async () => {
                      await assistantApi.decide(a, "revoke");
                    })
                  }
                >
                  撤销草稿
                </button>
              </div>
            )}
            {a.state === "UNKNOWN" && (
              <button
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    await assistantApi.decide(a, "reconcile");
                    setNotice("已查询供应商状态，没有重新提交操作。");
                  })
                }
              >
                核对供应商结果
              </button>
            )}
          </article>
        ))}
      </section>
      <section className="assistant-section">
        <h2>主动建议</h2>
        {signals.map((s) => (
          <article key={s.id} className="signal-card">
            <strong>
              {s.kind === "CALENDAR_CONFLICT" ? "日历冲突" : "重要邮件"} ·
              重要性 {s.importance}
            </strong>
            <p>{s.suggestion}</p>
            <button
              disabled={busy}
              onClick={() =>
                act(async () => {
                  await assistantApi.saveTask({
                    title: s.suggestion.slice(0, 200),
                    important: true,
                    urgent: s.kind === "CALENDAR_CONFLICT",
                    status: "TODO",
                    due_at: null,
                    run_id: s.run_id,
                    conversation_id: s.conversation_id,
                  });
                  setNotice("已加入四象限，可调整重要性与紧急性。");
                })
              }
            >
              加入四象限
            </button>
            <small>
              {s.reasons
                .map((r) =>
                  r === "PROVIDER_EVENTS_OVERLAP"
                    ? "日历服务返回的事件时间重叠"
                    : r === "PROVIDER_IMPORTANT_LABEL"
                      ? "邮件被服务标记为重要"
                      : r,
                )
                .join(" · ")}
            </small>
            <details>
              <summary>依据与关联</summary>
              <pre className="assistant-evidence">
                {JSON.stringify(
                  { correlation: s.correlation_key, evidence: s.evidence },
                  null,
                  2,
                )}
              </pre>
            </details>
          </article>
        ))}
        {!signals.length && (
          <p className="muted-text">检查连接服务后，重要变化会显示在这里。</p>
        )}
      </section>
      {prefs && (
        <section className="assistant-section">
          <h2>通知偏好</h2>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              act(async () => {
                setPrefs(await assistantApi.savePreferences(prefs));
                setNotice("通知偏好已保存。");
              });
            }}
          >
            <div className="assistant-fields">
              <label>
                <input
                  type="checkbox"
                  checked={prefs.enabled}
                  onChange={(e) =>
                    setPrefs({ ...prefs, enabled: e.target.checked })
                  }
                />
                通知重要变化
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={prefs.push_enabled}
                  onChange={(e) =>
                    setPrefs({ ...prefs, push_enabled: e.target.checked })
                  }
                />
                允许离线推送
              </label>
              <label>
                最低重要性
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={prefs.min_importance}
                  onChange={(e) =>
                    setPrefs({
                      ...prefs,
                      min_importance: Number(e.target.value),
                    })
                  }
                />
              </label>
              <label>
                免打扰开始
                <input
                  type="time"
                  value={prefs.quiet_start || ""}
                  onChange={(e) =>
                    setPrefs({ ...prefs, quiet_start: e.target.value || null })
                  }
                />
              </label>
              <label>
                免打扰结束
                <input
                  type="time"
                  value={prefs.quiet_end || ""}
                  onChange={(e) =>
                    setPrefs({ ...prefs, quiet_end: e.target.value || null })
                  }
                />
              </label>
              <label>
                时区
                <input
                  value={prefs.timezone}
                  onChange={(e) =>
                    setPrefs({ ...prefs, timezone: e.target.value })
                  }
                />
              </label>
            </div>
            <button disabled={busy} type="submit">
              保存偏好
            </button>
          </form>
          {native && (
            <button
              disabled={busy}
              onClick={() =>
                act(async () => {
                  const token = await requestPush();
                  const result = await assistantApi.registerPush(token);
                  localStorage.setItem("adex.pushDevice", result.id);
                  setNotice(
                    result.availability === "BLOCKED_EXTERNAL"
                      ? "设备已登记，但 APNs 服务尚未接通。"
                      : "已登记设备；真实送达需 APNs 与签名验证。",
                  );
                })
              }
            >
              授权并登记 iOS 通知
            </button>
          )}
        </section>
      )}
    </div>
  );
}
