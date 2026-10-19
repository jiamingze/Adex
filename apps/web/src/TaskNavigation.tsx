import type { Page } from "./navigation";
export function TaskNavigation({
  page,
  onNavigate,
}: {
  page: Page;
  onNavigate: (page: Page) => void;
}) {
  return (
    <nav className="workspace-segments" aria-label="任务分类">
      <button
        aria-current={page === "matrix" ? "page" : undefined}
        onClick={() => onNavigate("matrix")}
      >
        我的待办
      </button>
      <button
        aria-current={page === "tasks" ? "page" : undefined}
        onClick={() => onNavigate("tasks")}
      >
        自动安排
      </button>
    </nav>
  );
}
