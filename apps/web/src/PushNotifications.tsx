import { useEffect, useState } from "react";
import { request } from "./api";
import { native, requestPush } from "./platform";
import { assistantApi } from "./assistantApi";

type Status = {
  availability: string;
  devices: number;
  deliveries: { status: string; error_code?: string }[];
};
export function PushNotifications({
  conversationId,
}: {
  conversationId?: string;
}) {
  const [status, setStatus] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  const refresh = () => request<Status>("/push/status").then(setStatus);
  useEffect(() => {
    void refresh().catch(() => setMessage("推送状态暂时无法读取"));
  }, []);
  async function act(work: () => Promise<void>) {
    setBusy(true);
    setMessage("");
    try {
      await work();
      await refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "推送设置未完成");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-label="任务消息推送">
      <h2>任务消息推送</h2>
      <p>定时任务完成或需要你处理时，通知会送到 iPhone；点击回到对应会话。</p>
      <p>
        {status?.availability === "BLOCKED_EXTERNAL"
          ? "服务端推送凭据尚未配置"
          : status
            ? `已登记 ${status.devices} 台设备`
            : "正在检查推送状态…"}
      </p>
      {native ? (
        <button
          type="button"
          disabled={busy}
          onClick={() =>
            void act(async () => {
              const device = await requestPush();
              const result = await assistantApi.registerPush(
                device.token,
                device.environment,
              );
              const prefs = await assistantApi.preferences();
              await assistantApi.savePreferences({
                ...prefs,
                enabled: true,
                push_enabled: true,
              });
              localStorage.setItem("adex.pushDevice", result.id);
              setMessage(
                result.availability === "BLOCKED_EXTERNAL"
                  ? "设备已登记，仍需完成服务端 APNs 配置。"
                  : "已开启任务推送，可发送测试通知验证。",
              );
            })
          }
        >
          {busy ? "处理中…" : "开启 iPhone 任务推送"}
        </button>
      ) : (
        <p>请在 iPhone 的 Adex 客户端开启系统通知权限。</p>
      )}
      <button
        type="button"
        disabled={busy || !conversationId || !status?.devices}
        onClick={() =>
          void act(async () => {
            await request("/push/test", "POST", {
              event_id: crypto.randomUUID(),
              conversation_id: conversationId,
            });
            setMessage(
              "测试通知已进入发送队列，请检查 iPhone 通知；这不代表已经送达。",
            );
          })
        }
      >
        发送测试通知
      </button>
      {status?.deliveries[0] && (
        <small>
          最近发送状态：{status.deliveries[0].status}
          {status.deliveries[0].error_code
            ? ` · ${status.deliveries[0].error_code}`
            : ""}
        </small>
      )}
      {message && <p role="status">{message}</p>}
    </section>
  );
}
