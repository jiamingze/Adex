import {
  Sun,
  MessageSquare,
  Check,
  NotebookPen,
  CalendarClock,
  Sparkles,
  Brain,
  Play,
  Settings2,
  ArrowRight,
  ShieldCheck,
} from "lucide-react";
import { pageLabels, type Page } from "./navigation";
import { useKeyboardVisibility } from "./useKeyboardVisibility";
const primary = [
  { id: "today", icon: Sun },
  { id: "chat", icon: MessageSquare },
  { id: "matrix", icon: Check },
  { id: "workspace", icon: NotebookPen },
] as const;
const secondary = [
  { id: "assistant", icon: Sparkles },
  { id: "tasks", icon: CalendarClock },
  { id: "memory", icon: Brain },
  { id: "tools", icon: Play },
  { id: "settings", icon: Settings2 },
] as const;
export function WorkspaceNavigation({
  page,
  onNavigate,
}: {
  page: Page;
  onNavigate: (page: Page) => void;
}) {
  return (
    <nav className="workspace-navigation" aria-label="工作空间导航">
      <div className="section-label">日常</div>
      {primary.map((item) => (
        <button
          className={`nav-item ${page === item.id ? "active" : ""}`}
          aria-current={page === item.id ? "page" : undefined}
          key={item.id}
          onClick={() => onNavigate(item.id)}
        >
          <item.icon size={18} />
          {pageLabels[item.id]}
        </button>
      ))}
      <div className="section-label">助手与个性化</div>
      {secondary.map((item) => (
        <button
          className={`nav-item ${page === item.id ? "active" : ""}`}
          aria-current={page === item.id ? "page" : undefined}
          key={item.id}
          onClick={() => onNavigate(item.id)}
        >
          <item.icon size={17} />
          {pageLabels[item.id]}
        </button>
      ))}
    </nav>
  );
}
export function MobileNavigation({
  page,
  onNavigate,
}: {
  page: Page;
  onNavigate: (page: Page) => void;
}) {
  const keyboardVisible = useKeyboardVisibility();
  return (
    <nav
      className={`mobile-tabbar ${keyboardVisible ? "keyboard-hidden" : ""}`}
      aria-label="快捷导航"
    >
      {primary.map((item) => (
        <button
          aria-current={page === item.id ? "page" : undefined}
          key={item.id}
          onClick={() => onNavigate(item.id)}
        >
          <item.icon size={20} />
          <span>
            {item.id === "matrix"
              ? "待办"
              : item.id === "workspace"
                ? "笔记"
                : pageLabels[item.id]}
          </span>
        </button>
      ))}
    </nav>
  );
}
export function AccountPrompt({ onSignIn }: { onSignIn: () => void }) {
  return (
    <div className="content-page account-prompt">
      <span className="today-orb">
        <ShieldCheck size={28} />
      </span>
      <h1>让 Adex 更了解你</h1>
      <p>
        登录后即可保存任务、管理个人记忆和连接服务，手机与网页使用同一份工作空间。
      </p>
      <button className="experience-primary" onClick={onSignIn}>
        登录或创建账户
        <ArrowRight size={16} />
      </button>
      <small>你仍然可以返回聊天，继续以访客身份使用。</small>
    </div>
  );
}
