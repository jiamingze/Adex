import { Button } from "@adex/ui-web";
import type { Schedule } from "./api";
/** Removal is explicit and distinct from pausing; the server receipt controls list updates. */
export function DeleteScheduleDialog({
  schedule,
  busy,
  error,
  onCancel,
  onConfirm,
}: {
  schedule: Schedule;
  busy: boolean;
  error: string;
  onCancel: () => void;
  onConfirm: () => Promise<void>;
}) {
  return (
    <div className="modal-backdrop">
      <section
        className="modal delete-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-schedule-title"
        onKeyDown={(event) => {
          if (event.key === "Escape" && !busy) onCancel();
        }}
      >
        <h2 id="delete-schedule-title">删除这个自动任务？</h2>
        <p>
          「{schedule.title}
          」将被永久删除，不再自动执行。已有执行记录保留，已完成的操作不会撤销。
        </p>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <div className="modal-footer">
          <Button autoFocus disabled={busy} onClick={onCancel}>
            保留任务
          </Button>
          <Button
            className="danger-button"
            disabled={busy}
            onClick={() => void onConfirm()}
          >
            {busy ? "正在删除…" : "永久删除"}
          </Button>
        </div>
      </section>
    </div>
  );
}
