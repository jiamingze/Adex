import { useState } from "react";
import { Button } from "@adex/ui-web";
import { ApiError, type Schedule } from "./api";
import type { components } from "../../../packages/contracts/core.generated";

type Changes = Omit<components["schemas"]["ScheduleUpdate"], "revision">;
type Condition = components["schemas"]["NotificationCondition"];
function localInput(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}
/** The server's revision-checked receipt, never the local draft, changes the task list. */
export function EditScheduleDialog({
  schedule,
  onClose,
  onSave,
}: {
  schedule: Schedule;
  onClose: () => void;
  onSave: (changes: Changes) => Promise<void>;
}) {
  const [title, setTitle] = useState(schedule.title);
  const [instruction, setInstruction] = useState(schedule.instruction);
  const [kind, setKind] = useState<"ONCE" | "DAILY" | "INTERVAL">(
    schedule.kind as "ONCE" | "DAILY" | "INTERVAL",
  );
  const [zone, setZone] = useState(schedule.timezone);
  const [time, setTime] = useState(schedule.local_time?.slice(0, 5) || "08:00");
  const [minutes, setMinutes] = useState(
    (schedule.interval_seconds || 3600) / 60,
  );
  const [when, setWhen] = useState(localInput(schedule.next_fire_at));
  const [policy, setPolicy] = useState(
    schedule.task_request?.notification_policy || "EVERY_RUN",
  );
  const [condition, setCondition] = useState<Condition>(
    schedule.task_request?.notification_condition || {
      description: "",
      operator: "semantic",
      threshold: "",
      unit: "",
    },
  );
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <div className="modal-backdrop">
      <form
        className="modal schedule-edit-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-schedule-title"
        onKeyDown={(e) => {
          if (e.key === "Escape" && !busy) onClose();
        }}
        onSubmit={async (e) => {
          e.preventDefault();
          if (busy) return;
          setError("");
          const changes: Changes = {};
          if (title !== schedule.title) changes.title = title;
          if (instruction !== schedule.instruction)
            changes.instruction = instruction;
          if (kind !== schedule.kind) changes.kind = kind;
          if (zone !== schedule.timezone) changes.timezone = zone;
          if (
            kind === "DAILY" &&
            (kind !== schedule.kind ||
              time !== schedule.local_time?.slice(0, 5))
          )
            changes.local_time = time;
          if (
            kind === "INTERVAL" &&
            (kind !== schedule.kind ||
              Math.round(minutes * 60) !== schedule.interval_seconds)
          )
            changes.interval_seconds = Math.round(minutes * 60);
          if (
            kind === "ONCE" &&
            (kind !== schedule.kind ||
              when !== localInput(schedule.next_fire_at))
          ) {
            if (!when || !Number.isFinite(new Date(when).getTime())) {
              setError("请选择有效的执行时间。");
              return;
            }
            changes.first_fire_at = new Date(when).toISOString();
          }
          const rule =
            condition.operator === "semantic"
              ? { ...condition, threshold: "", unit: "" }
              : condition;
          if (
            policy !== schedule.task_request?.notification_policy ||
            (policy === "CONDITION_MET" &&
              JSON.stringify(rule) !==
                JSON.stringify(schedule.task_request?.notification_condition))
          ) {
            changes.notification_policy =
              policy as Changes["notification_policy"];
            if (policy === "CONDITION_MET")
              changes.notification_condition = rule;
          }
          if (!Object.keys(changes).length) {
            onClose();
            return;
          }
          setBusy(true);
          try {
            await onSave(changes);
          } catch (e) {
            setError(
              e instanceof ApiError && e.code === "REVISION_CONFLICT"
                ? "任务刚刚已更新。你的修改仍保留在这里，请关闭后重新打开最新任务再修改。"
                : e instanceof ApiError && e.code === "SCHEDULE_IN_PAST"
                  ? "执行时间已过去，请选择未来时间。"
                  : "保存失败，请检查内容和网络后重试。",
            );
          } finally {
            setBusy(false);
          }
        }}
      >
        <header className="modal-heading">
          <Button
            type="button"
            className="schedule-edit-cancel"
            disabled={busy}
            onClick={onClose}
          >
            取消
          </Button>
          <h2 id="edit-schedule-title">编辑任务</h2>
          <Button
            type="submit"
            className="schedule-edit-done"
            aria-label="保存修改"
            disabled={busy}
          >
            {busy ? "保存中…" : "完成"}
          </Button>
        </header>
        <div className="schedule-edit-scroll">
          <fieldset disabled={busy} className="schedule-edit-fields">
            <div className="schedule-edit-group schedule-edit-content">
              <label>
                任务名称
                <input
                  required
                  maxLength={200}
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </label>
              <label>
                让 Adex 做什么
                <textarea
                  required
                  rows={3}
                  maxLength={16000}
                  value={instruction}
                  onChange={(e) => setInstruction(e.target.value)}
                />
              </label>
            </div>
            <div className="schedule-edit-group schedule-edit-options">
              <div className="form-row">
                <label>
                  执行频率
                  <select
                    value={kind}
                    onChange={(e) => setKind(e.target.value as typeof kind)}
                  >
                    <option value="ONCE">一次性</option>
                    <option value="DAILY">每天</option>
                    <option value="INTERVAL">固定间隔</option>
                  </select>
                </label>
                <label>
                  时区
                  <select
                    value={zone}
                    onChange={(e) => setZone(e.target.value)}
                  >
                    {Array.from(
                      new Set([
                        schedule.timezone,
                        "Asia/Shanghai",
                        "Asia/Tokyo",
                        "Europe/London",
                        "America/New_York",
                        "UTC",
                      ]),
                    ).map((z) => (
                      <option key={z}>{z}</option>
                    ))}
                  </select>
                </label>
              </div>
              {kind === "DAILY" ? (
                <label>
                  每天的执行时间（{zone}）
                  <input
                    type="time"
                    required
                    value={time}
                    onChange={(e) => setTime(e.target.value)}
                  />
                </label>
              ) : kind === "INTERVAL" ? (
                <label>
                  每隔多少分钟
                  <input
                    type="number"
                    min={1}
                    max={525600}
                    step="any"
                    required
                    value={minutes}
                    onChange={(e) => setMinutes(Number(e.target.value))}
                  />
                  <small>修改间隔后，从保存时刻重新计时。</small>
                </label>
              ) : (
                <label>
                  执行时间（设备本地时区）
                  <input
                    type="datetime-local"
                    required
                    value={when}
                    onChange={(e) => setWhen(e.target.value)}
                  />
                </label>
              )}
            </div>
            <div className="schedule-edit-group schedule-edit-notification">
              <label>
                通知方式
                <select
                  value={policy}
                  onChange={(e) => setPolicy(e.target.value)}
                >
                  <option value="EVERY_RUN">每次执行后通知</option>
                  <option value="CHANGES_ONLY">结果有更新时通知</option>
                  <option value="CONDITION_MET">仅满足条件时通知</option>
                </select>
              </label>
              {policy === "CONDITION_MET" && (
                <>
                  <label>
                    通知条件
                    <textarea
                      required
                      maxLength={1000}
                      rows={2}
                      value={condition.description}
                      onChange={(e) =>
                        setCondition({
                          ...condition,
                          description: e.target.value,
                        })
                      }
                    />
                  </label>
                  <label>
                    判断方式
                    <select
                      value={condition.operator}
                      onChange={(e) =>
                        setCondition({
                          ...condition,
                          operator: e.target.value as Condition["operator"],
                        })
                      }
                    >
                      <option value="semantic">由助手依据证据判断</option>
                      <option value="lt">低于</option>
                      <option value="lte">不高于</option>
                      <option value="gt">高于</option>
                      <option value="gte">不低于</option>
                      <option value="eq">等于</option>
                    </select>
                  </label>
                  {condition.operator !== "semantic" && (
                    <div className="form-row">
                      <label>
                        数值
                        <input
                          required
                          maxLength={50}
                          inputMode="decimal"
                          value={condition.threshold}
                          onChange={(e) =>
                            setCondition({
                              ...condition,
                              threshold: e.target.value,
                            })
                          }
                        />
                      </label>
                      <label>
                        单位
                        <input
                          required
                          maxLength={40}
                          placeholder="例如 USD/oz"
                          value={condition.unit}
                          onChange={(e) =>
                            setCondition({ ...condition, unit: e.target.value })
                          }
                        />
                      </label>
                    </div>
                  )}
                  <small>
                    不满足、无法核实或执行失败时不推送，结果仍回到原会话。
                  </small>
                </>
              )}
            </div>
          </fieldset>
        </div>
        <p className="muted-text schedule-edit-hint">
          保存后影响后续执行；已经开始的任务继续使用原内容。
        </p>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
      </form>
    </div>
  );
}
