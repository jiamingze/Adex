/** Two independent dimensions, shared by Today and the flat task list. */
export function TaskPriority({
  important,
  urgent,
}: {
  important: boolean;
  urgent: boolean;
}) {
  return (
    <span
      className={`priority-tag ${important && urgent ? "critical" : important ? "important" : urgent ? "urgent" : "normal"}`}
    >
      {important && urgent
        ? "优先处理"
        : important
          ? "重要"
          : urgent
            ? "紧急"
            : "常规"}
    </span>
  );
}
