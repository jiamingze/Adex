/** Central page contract shared by deep links, history and in-app navigation. */
export const pages = [
  "today",
  "chat",
  "tasks",
  "memory",
  "workspace",
  "tools",
  "settings",
  "matrix",
  "assistant",
] as const;
export type Page = (typeof pages)[number];
export const pageLabels: Record<Page, string> = {
  today: "今日",
  chat: "对话",
  tasks: "自动任务",
  memory: "个人记忆",
  workspace: "资料",
  tools: "音乐与工具",
  settings: "我的设置",
  matrix: "任务",
  assistant: "主动助手",
};
export function isPage(value: unknown): value is Page {
  return typeof value === "string" && pages.includes(value as Page);
}
export function routeFromPath(path: string): {
  page: Page;
  conversation: string;
} {
  const match =
    /^\/c\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\/?$/i.exec(
      path,
    );
  if (match) return { page: "chat", conversation: match[1] };
  const value = path.replace(/^\//, "").replace(/\/$/, "");
  if (value === "notes") return { page: "workspace", conversation: "" };
  return { page: isPage(value) ? value : "chat", conversation: "" };
}
export function pagePath(page: Page, conversation = "") {
  return page === "chat"
    ? conversation
      ? `/c/${conversation}`
      : "/"
    : page === "workspace"
      ? "/notes"
      : `/${page}`;
}
