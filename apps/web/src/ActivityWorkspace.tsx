import { useEffect, useSyncExternalStore } from "react";
import {
  Activity,
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  CircleAlert,
  RefreshCw,
} from "lucide-react";
import { activityResource } from "./assistantWorkspaceApi";
import "./assistantWorkspace.css";
const labels: Record<string, string> = {
  QUEUED: "等待执行",
  RUNNING: "正在处理",
  COMPLETED: "已完成",
  FAILED: "未完成",
  UNKNOWN: "结果待核对",
  HUMAN: "等待你处理",
  CANCELLED: "已取消",
};
export function ActivityWorkspace({
  onOpen,
}: {
  onOpen: (id: string) => void;
}) {
  const snap = useSyncExternalStore(
    activityResource.subscribe,
    activityResource.getSnapshot,
  );
  useEffect(() => {
    void activityResource.load().catch(() => {});
    const timer = setInterval(() => {
      if (document.visibilityState === "visible")
        void activityResource.load(true).catch(() => {});
    }, 10000);
    return () => clearInterval(timer);
  }, []);
  const runs = snap.data?.items ?? [];
  return (
    <section className="agent-workspace">
      <header className="agent-section-heading">
        <div>
          <h2>活动</h2>
          <p>正在做什么、结果如何，都有记录。</p>
        </div>
        <button
          aria-label="刷新活动"
          onClick={() => void activityResource.load(true).catch(() => {})}
        >
          <RefreshCw size={18} />
        </button>
      </header>
      <div className="agent-activity-status">
        <Activity size={18} />
        <strong>
          {runs.some((r) => r.status === "RUNNING")
            ? "Adex 正在处理你的安排"
            : "Adex 随时待命"}
        </strong>
        <span>{runs.filter((r) => r.status === "RUNNING").length} 进行中</span>
      </div>
      {!!snap.error && (
        <p className="experience-inline-error">活动更新失败，请刷新重试。</p>
      )}
      {snap.loading && !snap.data && <p role="status">正在读取活动…</p>}
      {!runs.length && !snap.loading && (
        <div className="agent-empty">
          <Clock3 size={28} />
          <h3>从一件交给 Adex 的事开始</h3>
          <p>聊天中创建的后台工作与定时安排会在这里留下执行记录。</p>
        </div>
      )}
      <div className="agent-timeline">
        {runs.map((r) => (
          <button
            key={r.id}
            className="agent-activity"
            onClick={() => onOpen(r.origin_conversation_id)}
          >
            <span className={`activity-marker state-${r.status.toLowerCase()}`}>
              {r.status === "COMPLETED" ? (
                <CheckCircle2 size={17} />
              ) : ["FAILED", "UNKNOWN", "HUMAN"].includes(r.status) ? (
                <CircleAlert size={17} />
              ) : (
                <Clock3 size={17} />
              )}
            </span>
            <span>
              <strong>{r.instruction}</strong>
              <small>
                {new Date(r.created_at).toLocaleString("zh-CN")} ·{" "}
                {labels[r.status] || r.status}
                {r.checkpoint_ref ? " · 可恢复记录已保存" : ""}
              </small>
            </span>
            <ArrowUpRight size={16} />
          </button>
        ))}
      </div>
    </section>
  );
}
