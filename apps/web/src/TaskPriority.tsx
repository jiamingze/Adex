/** Two independent dimensions, shared by Today and the flat task list. */
export function TaskPriority({
  important,
  urgent,
}: {
  important: boolean;
  urgent: boolean;
}) {
  return (
    <span className="priority-pair">
      <span className={`priority-tag ${important ? "important" : "normal"}`}>
        {important ? "重要" : "不重要"}
      </span>
      <span className={`priority-tag ${urgent ? "critical" : "normal"}`}>
        {urgent ? "紧急" : "不紧急"}
      </span>
    </span>
  );
}
