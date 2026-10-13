import { useState, useEffect } from "react";
import { accountApi, type Conversation } from "./api";
import { preferences, applyPreferences } from "./preferences";
import { Button } from "@adex/ui-web";
import { ArrowRight, Brain, Link2, Bell } from "lucide-react";
import { AccountPrompt } from "./WorkspaceNavigation";
import type { Page } from "./navigation";
import type { AssistantTab } from "./AssistantHub";
export function Settings({
  conversations,
  guest,
  onSignIn,
  onNavigate,
  onAssistant,
}: {
  conversations: Conversation[];
  guest: boolean;
  onSignIn: () => void;
  onNavigate: (page: Page) => void;
  onAssistant: (tab: AssistantTab) => void;
}) {
  const [tab, setTab] = useState("常规"),
    [prefs, setPrefs] = useState(preferences),
    [notice, setNotice] = useState(""),
    [saving, setSaving] = useState(false);
  const [settings, setSettings] = useState({
      memory_enabled: true,
      email_notifications: false,
      email: "",
    }),
    [usage, setUsage] = useState<unknown>({}),
    [error, setError] = useState(""),
    [monitors, setMonitors] = useState<
      { id: string; query: string; keyword: string; active: boolean }[]
    >([]),
    [query, setQuery] = useState(""),
    [keyword, setKeyword] = useState(""),
    [conv, setConv] = useState(conversations[0]?.id || "");
  const [mode, setMode] = useState("SEARCH"),
    [lat, setLat] = useState(31.23),
    [lon, setLon] = useState(121.47),
    [threshold, setThreshold] = useState(30),
    [metric, setMetric] = useState("temperature_2m"),
    [operator, setOperator] = useState("gte");
  const [settingsReady, setSettingsReady] = useState(false);
  async function refresh() {
    const [s, u, m] = await Promise.all([
      accountApi.settings(),
      accountApi.usage(),
      accountApi.monitors(),
    ]);
    setSettings({ ...s.settings, email: s.settings.email || "" });
    setUsage(u);
    setMonitors(m.items);
    setSettingsReady(true);
  }
  useEffect(() => {
    if (!guest)
      refresh().catch(() => setError("暂时无法读取账户设置，请稍后刷新重试。"));
  }, [guest]);
  useEffect(() => {
    if (!conv && conversations[0]) setConv(conversations[0].id);
  }, [conversations, conv]);
  const metrics = usage as {
    model?: {
      status?: string;
      tokens?: { input_tokens: number; output_tokens: number };
      states?: { calls: number }[];
      daily_call_limit?: number;
      estimated_cost?: string | null;
      currency?: string;
    };
    storage?: { used_bytes: number; quota_bytes: number };
    tools?: { reserved_tool_units: number; daily_tool_unit_limit: number };
  };
  const changePrefs = (value: typeof prefs) => {
    setPrefs(value);
    applyPreferences(value);
    setNotice("偏好已保存到当前设备");
  };
  return (
    <div className="content-page">
      <h1>设置</h1>
      <p className="settings-subtitle">
        按你的习惯，调整助手的外观、记忆与通知。
      </p>
      <div className="settings-layout">
        <nav className="settings-tabs" aria-label="设置分类">
          {["常规", "个性化", "通知", "用量", "安全", "监控"].map((t) => (
            <button
              key={t}
              className={tab === t ? "active" : ""}
              aria-current={tab === t ? "page" : undefined}
              onClick={() => {
                setTab(t);
                setNotice("");
                setError("");
              }}
            >
              {t}
            </button>
          ))}
        </nav>
        <section className="settings-section">
          {guest && tab !== "常规" ? (
            <AccountPrompt onSignIn={onSignIn} />
          ) : (
            <>
              {notice && (
                <p className="save-note" role="status">
                  {notice}
                </p>
              )}
              {tab === "常规" && (
                <>
                  <h2>常规</h2>
                  <p>调整外观与聊天方式，偏好会保存在当前设备。</p>
                  <div className="setting-row">
                    <div>
                      <strong>外观</strong>
                      <p>选择适合你的主题</p>
                    </div>
                    <select
                      aria-label="外观"
                      value={prefs.theme}
                      onChange={(e) =>
                        changePrefs({
                          ...prefs,
                          theme: e.target.value as typeof prefs.theme,
                        })
                      }
                    >
                      <option value="system">跟随系统</option>
                      <option value="light">浅色</option>
                      <option value="dark">深色</option>
                    </select>
                  </div>
                  <div className="setting-row">
                    <div>
                      <strong>Enter 发送消息</strong>
                      <p>关闭后使用 Ctrl / ⌘ + Enter 发送</p>
                    </div>
                    <input
                      aria-label="Enter 发送消息"
                      type="checkbox"
                      checked={prefs.enterSend}
                      onChange={(e) =>
                        changePrefs({ ...prefs, enterSend: e.target.checked })
                      }
                    />
                  </div>
                </>
              )}
              {tab === "常规" && (
                <div className="settings-shortcuts">
                  <h3>你的助手</h3>
                  <button onClick={() => onNavigate("memory")}>
                    <Brain size={18} />
                    <span>
                      <strong>个人记忆</strong>
                      <small>查看、纠正或删除助手记住的偏好</small>
                    </span>
                    <ArrowRight size={15} />
                  </button>
                  <button onClick={() => onAssistant("connections")}>
                    <Link2 size={18} />
                    <span>
                      <strong>连接我的服务</strong>
                      <small>管理日历、邮件和操作权限</small>
                    </span>
                    <ArrowRight size={15} />
                  </button>
                  <button onClick={() => onAssistant("preferences")}>
                    <Bell size={18} />
                    <span>
                      <strong>主动提醒与免打扰</strong>
                      <small>选择何时、通过什么方式接收提醒</small>
                    </span>
                    <ArrowRight size={15} />
                  </button>
                </div>
              )}
              {error && <p role="alert">{error}</p>}
              {(tab === "个性化" || tab === "通知") && (
                <form
                  className="workspace-form"
                  onSubmit={async (e) => {
                    e.preventDefault();
                    setSaving(true);
                    setError("");
                    try {
                      await accountApi.save(settings);
                      setNotice("设置已保存");
                    } catch (e) {
                      setError("操作未完成，请检查连接后重试。");
                    } finally {
                      setSaving(false);
                    }
                  }}
                >
                  <h2>{tab === "个性化" ? "记忆与个性化" : "通知偏好"}</h2>
                  {tab === "个性化" && (
                    <label>
                      <input
                        type="checkbox"
                        checked={settings.memory_enabled}
                        onChange={(e) =>
                          setSettings({
                            ...settings,
                            memory_enabled: e.target.checked,
                          })
                        }
                      />
                      使用长期记忆与自动明确记忆提取
                    </label>
                  )}
                  {tab === "通知" && (
                    <>
                      <label>
                        <input
                          type="checkbox"
                          checked={settings.email_notifications}
                          onChange={(e) =>
                            setSettings({
                              ...settings,
                              email_notifications: e.target.checked,
                            })
                          }
                        />
                        接收离线任务邮件
                      </label>
                      <label>
                        通知邮箱
                        <input
                          type="email"
                          value={settings.email}
                          onChange={(e) =>
                            setSettings({ ...settings, email: e.target.value })
                          }
                        />
                      </label>
                    </>
                  )}
                  <p>
                    记忆由你掌控，可在记忆页面查看和删除。邮件通知需配置邮件服务后才能送达。
                  </p>
                  <Button disabled={saving || !settingsReady}>
                    {saving ? "保存中…" : "保存设置"}
                  </Button>
                </form>
              )}
              {tab === "用量" && (
                <>
                  <h2>用量与存储</h2>
                  <p>今日模型调用与工具额度。金额仅在已配置计价时显示。</p>
                  <div className="usage-grid">
                    <article>
                      <span>模型调用</span>
                      <strong>
                        {!metrics.model
                          ? "—"
                          : metrics.model.status === "UNAVAILABLE"
                            ? "暂不可用"
                            : (metrics.model?.states || []).reduce(
                                (n, s) => n + s.calls,
                                0,
                              )}
                      </strong>
                      <small>
                        {metrics.model?.daily_call_limit === 0
                          ? "未限制回复次数"
                          : `每日上限 ${metrics.model?.daily_call_limit ?? "—"} 次`}
                      </small>
                    </article>
                    <article>
                      <span>输入 / 输出 Token</span>
                      <strong>
                        {metrics.model?.tokens?.input_tokens.toLocaleString() ??
                          "—"}
                      </strong>
                      <small>
                        输出{" "}
                        {metrics.model?.tokens?.output_tokens.toLocaleString() ??
                          "—"}
                      </small>
                    </article>
                    <article>
                      <span>工具额度</span>
                      <strong>
                        {metrics.tools?.reserved_tool_units ?? "—"}
                      </strong>
                      <small>
                        每日上限 {metrics.tools?.daily_tool_unit_limit ?? "—"}
                      </small>
                    </article>
                    <article>
                      <span>文件存储</span>
                      <strong>
                        {metrics.storage
                          ? `${(metrics.storage.used_bytes / 1048576).toFixed(1)} MB`
                          : "—"}
                      </strong>
                      <progress
                        value={metrics.storage?.used_bytes || 0}
                        max={metrics.storage?.quota_bytes || 1}
                      />
                      <small>
                        共{" "}
                        {metrics.storage
                          ? Math.round(metrics.storage.quota_bytes / 1048576)
                          : "—"}{" "}
                        MB
                      </small>
                    </article>
                  </div>
                  <p>
                    估算费用：
                    {metrics.model?.estimated_cost == null
                      ? "未配置计价"
                      : `${metrics.model.estimated_cost} ${metrics.model.currency}`}
                  </p>
                  <Button
                    onClick={() =>
                      refresh().catch((e) =>
                        setError("操作未完成，请检查连接后重试。"),
                      )
                    }
                  >
                    刷新用量
                  </Button>
                </>
              )}
              {tab === "安全" && (
                <>
                  <h2>登录与安全</h2>
                  <p>
                    撤销其他登录后，其他设备需要重新输入账号密码。当前会话保持登录。
                  </p>
                  <Button
                    onClick={async () => {
                      try {
                        await accountApi.revoke();
                        setNotice("其他登录会话已撤销");
                      } catch (e) {
                        setError("操作未完成，请检查连接后重试。");
                      }
                    }}
                  >
                    退出其他设备
                  </Button>
                </>
              )}
              {tab === "监控" && (
                <>
                  <form
                    className="workspace-form"
                    onSubmit={async (e) => {
                      e.preventDefault();
                      try {
                        await accountApi.monitor({
                          query: query || "天气监控",
                          keyword: keyword || "天气阈值",
                          kind: mode,
                          latitude: lat,
                          longitude: lon,
                          threshold,
                          metric,
                          operator,
                          origin_conversation_id: conv,
                        });
                        await refresh();
                        setQuery("");
                        setKeyword("");
                      } catch (e) {
                        setError("操作未完成，请检查连接后重试。");
                      }
                    }}
                  >
                    <h2>条件监控</h2>
                    <label>
                      监控类型
                      <select
                        value={mode}
                        onChange={(e) => setMode(e.target.value)}
                      >
                        <option value="SEARCH">关键词与动态</option>
                        <option value="WEATHER">天气阈值</option>
                      </select>
                    </label>
                    {mode === "WEATHER" && (
                      <div className="form-row">
                        <label>
                          纬度
                          <input
                            type="number"
                            step="any"
                            min={-90}
                            max={90}
                            value={lat}
                            onChange={(e) => setLat(Number(e.target.value))}
                          />
                        </label>
                        <label>
                          经度
                          <input
                            type="number"
                            step="any"
                            min={-180}
                            max={180}
                            value={lon}
                            onChange={(e) => setLon(Number(e.target.value))}
                          />
                        </label>
                        <label>
                          指标
                          <select
                            value={metric}
                            onChange={(e) => setMetric(e.target.value)}
                          >
                            <option value="temperature_2m">气温 °C</option>
                            <option value="precipitation">降水 mm</option>
                            <option value="wind_speed_10m">风速 km/h</option>
                          </select>
                        </label>
                        <label>
                          条件
                          <select
                            value={operator}
                            onChange={(e) => setOperator(e.target.value)}
                          >
                            <option value="gte">大于等于</option>
                            <option value="lte">小于等于</option>
                          </select>
                        </label>
                        <label>
                          阈值
                          <input
                            type="number"
                            step="any"
                            value={threshold}
                            onChange={(e) =>
                              setThreshold(Number(e.target.value))
                            }
                          />
                        </label>
                      </div>
                    )}
                    <label>
                      搜索来源主题
                      <input
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        maxLength={300}
                        required={mode === "SEARCH"}
                      />
                    </label>
                    <label>
                      出现以下关键词时通知
                      <input
                        value={keyword}
                        onChange={(e) => setKeyword(e.target.value)}
                        maxLength={100}
                        required={mode === "SEARCH"}
                      />
                    </label>
                    <label>
                      接收会话
                      <select
                        value={conv}
                        onChange={(e) => setConv(e.target.value)}
                      >
                        {conversations.map((c) => (
                          <option value={c.id} key={c.id}>
                            {c.title}
                          </option>
                        ))}
                      </select>
                    </label>
                    <p>
                      同主题共享采集，每 15 分钟检查。相同内容去重，通知间隔至少
                      1 小时。
                    </p>
                    <Button disabled={!conv}>创建监控</Button>
                  </form>
                  {monitors
                    .filter((m) => m.active)
                    .map((m) => (
                      <article className="workspace-card" key={m.id}>
                        <strong>{m.query}</strong>
                        <p>关键词：{m.keyword}</p>
                        <Button
                          onClick={async () => {
                            await accountApi.cancelMonitor(m.id);
                            await refresh();
                          }}
                        >
                          取消监控
                        </Button>
                      </article>
                    ))}
                  {!monitors.some((m) => m.active) && (
                    <p className="muted-text">还没有正在运行的监控。</p>
                  )}
                </>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
}
