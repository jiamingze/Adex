package io.adex.app.productivity;

import io.adex.kernel.Kernel;
import java.sql.Timestamp;
import java.time.*;
import java.util.*;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

/** Publishes todo changes to Automation; this is an outbox bridge, never a deadline scheduler. */
@Service
public class MatrixReminderService {
  private final Kernel k;

  public MatrixReminderService(Kernel k) {
    this.k = k;
  }

  public void enqueue(Map<String, Object> task) {
    if (!Boolean.TRUE.equals(task.get("important"))
        || !"TODO".equals(task.get("status"))
        || task.get("due_at") == null) return;
    k.db.update(
        "INSERT INTO matrix_reminders(id,task_id,owner_id,due_at,conversation_id) SELECT gen_random_uuid(),id,owner_id,due_at,conversation_id FROM matrix_tasks WHERE id=? AND due_at>clock_timestamp() ON CONFLICT DO NOTHING",
        task.get("id"));
    k.db.update(
        "INSERT INTO outbox(id,kind,resource_id) SELECT gen_random_uuid(),'matrix.reminder',id FROM matrix_reminders WHERE task_id=? ON CONFLICT DO NOTHING",
        task.get("id"));
  }

  @Scheduled(fixedDelay = 1500)
  public void publish() {
    for (int i = 0; i < 20; i++) {
      Map<String, Object> event;
      try {
        event =
            k.tx.execute(
                tx -> {
                  var rows =
                      k.db.queryForList(
                          "SELECT id FROM outbox WHERE kind='matrix.reminder' AND delivered_at IS NULL AND next_attempt_at<=clock_timestamp() AND (lease_until IS NULL OR lease_until<clock_timestamp()) ORDER BY next_attempt_at FOR UPDATE SKIP LOCKED LIMIT 1");
                  if (rows.isEmpty()) return null;
                  return k.row(
                      "UPDATE outbox SET lease_until=clock_timestamp()+interval '30 seconds',claim_id=?,attempt_count=attempt_count+1 WHERE id=? RETURNING *",
                      Kernel.id(),
                      rows.getFirst().get("id"));
                });
        if (event == null) return;
      } catch (Exception unavailable) {
        return;
      }
      try {
        var rows =
            k.db.queryForList(
                "SELECT r.* FROM matrix_reminders r JOIN matrix_tasks t ON t.id=r.task_id AND t.owner_id=r.owner_id WHERE r.id=? AND t.important AND t.status='TODO' AND t.due_at=r.due_at AND t.due_at>clock_timestamp()",
                event.get("resource_id"));
        if (!rows.isEmpty()) {
          var reminder = rows.getFirst();
          UUID owner = Kernel.uuid(reminder.get("owner_id"));
          UUID conv = conversation(reminder);
          // Immutable due/created times keep request_hash stable across HTTP ambiguity/retry.
          Instant fire = ((Timestamp) reminder.get("due_at")).toInstant().minusSeconds(600);
          Instant created = ((Timestamp) reminder.get("created_at")).toInstant();
          if (fire.isBefore(created)) fire = created;
          var body = new LinkedHashMap<String, Object>();
          body.put("title", "重要待办到期提醒");
          body.put("instruction", "发送待办截止前提醒");
          body.put("kind", "ONCE");
          body.put("timezone", "Asia/Shanghai");
          body.put("first_fire_at", fire.toString());
          body.put("origin_conversation_id", conv);
          body.put("idempotency_key", "matrix-reminder:" + reminder.get("id"));
          body.put("task_kind", "MATRIX_REMINDER");
          body.put("task_request", Map.of("matrix_reminder_id", reminder.get("id")));
          k.call(
              "automation", "schedule:write", owner, null, "POST", "/internal/automations", body);
        }
        k.db.update(
            "UPDATE outbox SET delivered_at=clock_timestamp(),lease_until=NULL WHERE id=? AND claim_id=?",
            event.get("id"),
            event.get("claim_id"));
      } catch (Exception failure) {
        k.db.update(
            "UPDATE outbox SET lease_until=NULL,next_attempt_at=clock_timestamp()+make_interval(secs=>least(60,attempt_count*2)) WHERE id=? AND claim_id=?",
            event.get("id"),
            event.get("claim_id"));
      }
    }
  }

  private UUID conversation(Map<String, Object> reminder) {
    if (reminder.get("conversation_id") != null)
      return Kernel.uuid(reminder.get("conversation_id"));
    return k.tx.execute(
        tx -> {
          UUID owner = Kernel.uuid(reminder.get("owner_id"));
          k.db.queryForObject(
              "SELECT pg_advisory_xact_lock(hashtextextended(?,0))",
              Object.class,
              "matrix-inbox:" + owner);
          var rows =
              k.db.queryForList(
                  "SELECT c.id FROM matrix_reminder_inboxes i JOIN conversations c ON c.id=i.conversation_id WHERE i.owner_id=? AND c.deleted_at IS NULL",
                  owner);
          UUID conv;
          if (rows.isEmpty()) {
            conv = Kernel.id();
            k.db.update(
                "INSERT INTO conversations(id,owner_id,title) VALUES(?,?,?)", conv, owner, "待办提醒");
            k.db.update(
                "INSERT INTO matrix_reminder_inboxes(owner_id,conversation_id) VALUES(?,?) ON CONFLICT(owner_id) DO UPDATE SET conversation_id=excluded.conversation_id",
                owner,
                conv);
          } else conv = Kernel.uuid(rows.getFirst().get("id"));
          k.db.update(
              "UPDATE matrix_reminders SET conversation_id=? WHERE id=? AND conversation_id IS NULL",
              conv,
              reminder.get("id"));
          return conv;
        });
  }
}
