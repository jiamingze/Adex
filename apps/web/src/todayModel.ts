/** Presentation-only projection: PostgreSQL/API state remains authoritative. */
export function focusTasks<
  T extends {
    status: string;
    important: boolean;
    urgent: boolean;
    due_at: string | null;
  },
>(tasks: T[]): T[] {
  return tasks
    .filter((t) => t.status === "TODO")
    .sort((a, b) => {
      const priority = (t: T) => Number(t.important) * 2 + Number(t.urgent);
      return (
        priority(b) - priority(a) ||
        (a.due_at ? Date.parse(a.due_at) : Infinity) -
          (b.due_at ? Date.parse(b.due_at) : Infinity)
      );
    });
}
export function isDueToday(iso: string | null, now = new Date()) {
  return !!iso && new Date(iso).toDateString() === now.toDateString();
}
export function dueCaption(iso: string | null, now = new Date()) {
  if (!iso) return "未设截止时间";
  const date = new Date(iso);
  if (date.getTime() < now.getTime()) return "已逾期";
  return isDueToday(iso, now)
    ? `今天 ${date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`
    : date.toLocaleString("zh-CN", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
}
export function awaitingAction<T extends { state: string; expires_at: string }>(
  actions: T[],
  now = new Date(),
) {
  return actions.filter(
    (a) =>
      a.state === "UNKNOWN" ||
      (a.state === "PENDING" && Date.parse(a.expires_at) > now.getTime()),
  );
}

/** Visible editable draft, never an automatic model call or task execution. */
export function planningPrompt(
  snapshot: {
    tasks:
      | {
          title: string;
          status: string;
          important: boolean;
          urgent: boolean;
          due_at: string | null;
        }[]
      | null;
    schedules:
      | {
          title: string;
          status: string;
          next_fire_at: string | null;
          timezone: string;
        }[]
      | null;
  },
  asOf: Date,
) {
  const lines = [
    "根据以下工作空间快照，帮我安排今天最值得优先处理的事，给出简洁的行动建议。",
    "尚未读取的内容不要当作没有，也不要推测我的日历、邮件或健康情况。先给建议，需要新建任务或对外操作时再让我确认。",
    `快照时间：${asOf.toISOString()}`,
  ];
  lines.push("待办：");
  if (snapshot.tasks === null) lines.push("暂不可用，未获取待办信息。");
  else {
    const tasks = focusTasks(snapshot.tasks).slice(0, 8);
    if (!tasks.length) lines.push("当前已保存的待办为空。");
    for (const task of tasks)
      lines.push(
        `- ${task.title.slice(0, 200)}；${task.important ? "重要" : "非重要"}；${task.urgent ? "紧急" : "非紧急"}；截止：${task.due_at ?? "未设置"}`,
      );
  }
  lines.push("已启用的自动任务（不是日历事件）：");
  if (snapshot.schedules === null) lines.push("暂不可用，未获取自动任务信息。");
  else {
    const schedules = snapshot.schedules
      .filter((s) => s.status === "ACTIVE")
      .slice(0, 5);
    if (!schedules.length) lines.push("当前没有已启用的自动任务。");
    for (const schedule of schedules)
      lines.push(
        `- ${schedule.title.slice(0, 200)}；下次：${schedule.next_fire_at ?? "未确定"}；时区：${schedule.timezone}`,
      );
  }
  return lines.join("\n");
}
