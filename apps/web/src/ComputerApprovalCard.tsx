import { useEffect, useState } from "react";
import { assistantApi, type Action } from "./assistantApi";

export function ComputerApprovalCard({ id }: { id: string }) {
  const [action, setAction] = useState<Action | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const load = async () => {
    const result = await assistantApi.actions();
    setAction(result.items.find((item) => item.id === id) || null);
  };
  useEffect(() => {
    void load().catch(() => setMessage("暂时无法读取操作，请稍后重试。"));
  }, [id]);
  const decide = async (decision: string) => {
    if (!action || busy) return;
    setBusy(true);
    try {
      await assistantApi.decide(action, decision);
      setMessage(
        decision === "approve"
          ? "已确认，Adex 将继续操作。"
          : "已停止本次操作。",
      );
      await load();
    } catch {
      setMessage("尚未提交，请稍后重试；过期操作需要重新准备。");
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="computer-action-card">
      <strong>确认 Mac 操作</strong>
      {action ? (
        <>
          <dl>
            {Object.entries(action.request.payload)
              .filter(([key, value]) => key !== "element_id" && String(value).length > 0)
              .map(([key, value]) => (
              <div key={key}>
                <dt>
                  {{
                    app: "应用",
                    control: "控件",
                    action: "操作",
                    element_id: "控件编号",
                    text: "输入内容",
                  }[key] || key}
                </dt>
                <dd>{key === "action" ? ({ press: "点击", set_value: "填写内容" }[String(value)] || String(value)) : String(value)}</dd>
              </div>
            ))}
          </dl>
          {action.state === "PENDING" && (
            <div className="task-actions">
              <button
                className="button primary"
                disabled={busy}
                onClick={() => void decide("approve")}
              >
                确认并继续
              </button>
              <button
                className="button"
                disabled={busy}
                onClick={() => void decide("revoke")}
              >
                取消操作
              </button>
            </div>
          )}
          {action.state !== "PENDING" && (
            <p role="status">{{ APPROVED: "已确认，等待继续", SUCCEEDED: "该动作已执行", REVOKED: "已取消", UNKNOWN: "执行结果待人工核对", EXPIRED: "操作已过期" }[action.state] || "操作状态：" + action.state}</p>
          )}
          <small>仅授权这一个动作；界面变化或超时后不会自动重复。</small>
        </>
      ) : (
        <p>{message || "正在读取操作…"}</p>
      )}
      {action && message && <p role="status">{message}</p>}
    </section>
  );
}
