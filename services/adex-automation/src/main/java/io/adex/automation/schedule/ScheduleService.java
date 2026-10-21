package io.adex.automation.schedule;

import io.adex.kernel.Kernel;
import java.sql.Timestamp;
import java.time.*;
import java.util.*;
import org.springframework.stereotype.Service;

/** Owns Schedule transaction boundaries. Claims are verified by the HTTP adapter. */
@Service
public class ScheduleService {
  private final Kernel k;

  public ScheduleService(Kernel k) {
    this.k = k;
  }

  public Object list(Map<String, Object> claims) {
    return Kernel.items(
        k.db.queryForList(
            "SELECT * FROM schedules WHERE owner_id=? AND task_kind<>'MATRIX_REMINDER' ORDER BY created_at DESC LIMIT 100",
            Kernel.uuid(claims.get("owner"))));
  }

  public Object create(Map<String, Object> claims, Map<String, Object> b) {
    UUID owner = Kernel.uuid(claims.get("owner")),
        conv = Kernel.uuid(b.get("origin_conversation_id"));
    String title = Kernel.text(b, "title", 200),
        instruction = Kernel.text(b, "instruction", 16000),
        kind = Kernel.text(b, "kind", 20),
        tz = Kernel.text(b, "timezone", 80),
        key = Kernel.text(b, "idempotency_key", 128);
    ZoneId.of(tz);
    if (!Set.of("ONCE", "INTERVAL", "DAILY").contains(kind))
      throw Kernel.error(400, "INVALID_SCHEDULE_KIND");
    Instant first = Instant.parse(Kernel.text(b, "first_fire_at", 80));
    int seconds =
        kind.equals("INTERVAL") ? Math.toIntExact(Kernel.number(b, "interval_seconds")) : 0;
    if (kind.equals("INTERVAL") && (seconds < 60 || seconds > 31536000))
      throw Kernel.error(400, "INVALID_INTERVAL");
    LocalTime time =
        kind.equals("DAILY") ? LocalTime.parse(Kernel.text(b, "local_time", 20)) : null;
    String taskKind = String.valueOf(b.getOrDefault("task_kind", "CHAT"));
    if (!Set.of("CHAT", "CONNECTOR_SYNC", "MATRIX_REMINDER").contains(taskKind))
      throw Kernel.error(400, "INVALID_TASK_KIND");
    Object taskRequest = NotificationRules.request(b);
    if (taskKind.equals("CONNECTOR_SYNC")
        && (!(taskRequest instanceof Map<?, ?> request) || request.get("connection_id") == null))
      throw Kernel.error(400, "INVALID_CONNECTOR_SCHEDULE");
    if (taskKind.equals("MATRIX_REMINDER")
        && (!kind.equals("ONCE")
            || !(taskRequest instanceof Map<?, ?> reminder)
            || Kernel.uuid(reminder.get("matrix_reminder_id")) == null))
      throw Kernel.error(400, "INVALID_REMINDER_SCHEDULE");
    String hash = Kernel.hash(k.encode(new TreeMap<>(b)));
    return k.tx.execute(
        s -> {
          // Serialize owner+key only, independent of schedulers and other owners.
          k.db.queryForObject(
              "SELECT pg_advisory_xact_lock(hashtextextended(?,0))",
              Object.class,
              owner + ":" + key);
          if (k.db.queryForObject(
                  "SELECT count(*) FROM deleted_schedules WHERE owner_id=? AND idempotency_key=?",
                  Integer.class,
                  owner,
                  key)
              > 0) throw Kernel.error(410, "SCHEDULE_DELETED");
          var existing =
              k.db.queryForList(
                  "SELECT * FROM schedules WHERE owner_id=? AND idempotency_key=?", owner, key);
          if (!existing.isEmpty()) {
            var v = existing.getFirst();
            if (!hash.equals(v.get("request_hash")))
              throw Kernel.error(409, "IDEMPOTENCY_CONFLICT");
            return v;
          }
          Instant now =
              k.db.queryForObject("SELECT clock_timestamp()", Timestamp.class).toInstant();
          if (!taskKind.equals("MATRIX_REMINDER") && first.isBefore(now.minusSeconds(5)))
            throw Kernel.error(400, "SCHEDULE_IN_PAST");
          if (k.db.queryForObject(
                      "SELECT count(*) FROM schedules WHERE owner_id=? AND status IN"
                          + " ('ACTIVE','PAUSED') AND task_kind<>'MATRIX_REMINDER'",
                      Integer.class,
                      owner)
                  >= 100
              && !taskKind.equals("MATRIX_REMINDER")) throw Kernel.error(429, "SCHEDULE_LIMIT");
          Instant next =
              kind.equals("DAILY") ? ScheduleTime.nextDaily(first.minusNanos(1), tz, time) : first;
          UUID id = Kernel.id();
          k.db.update(
              "INSERT INTO"
                  + " schedules(id,owner_id,origin_conversation_id,title,instruction,kind,timezone,local_time,interval_seconds,next_fire_at,idempotency_key,request_hash)"
                  + " VALUES(?,?,?,?,?,?,?,?::time,?,?,?,?)",
              id,
              owner,
              conv,
              title,
              instruction,
              kind,
              tz,
              time == null ? null : time.toString(),
              kind.equals("INTERVAL") ? seconds : null,
              Timestamp.from(next),
              key,
              hash);
          k.db.update(
              "UPDATE schedules SET task_kind=?,task_request=?::jsonb WHERE id=?",
              taskKind,
              k.encode(taskRequest),
              id);
          return k.row("SELECT * FROM schedules WHERE id=?", id);
        });
  }

  public Object update(Map<String, Object> claims, UUID id, Map<String, Object> b) {
    UUID owner = Kernel.uuid(claims.get("owner"));
    String status = b.containsKey("status") ? Kernel.text(b, "status", 20) : null;
    if (status != null && !Set.of("ACTIVE", "PAUSED", "CANCELLED").contains(status))
      throw Kernel.error(400, "INVALID_STATUS");
    var editable =
        Set.of(
            "revision",
            "status",
            "title",
            "instruction",
            "kind",
            "timezone",
            "local_time",
            "interval_seconds",
            "first_fire_at",
            "notification_policy",
            "notification_condition");
    if (!editable.containsAll(b.keySet())) throw Kernel.error(400, "INVALID_SCHEDULE_FIELDS");
    if (b.keySet().stream().allMatch("revision"::equals))
      throw Kernel.error(400, "EMPTY_SCHEDULE_UPDATE");
    if (b.containsKey("notification_condition") && !b.containsKey("notification_policy"))
      throw Kernel.error(400, "INVALID_NOTIFICATION_CONDITION");
    long rev = Kernel.number(b, "revision");
    return k.tx.execute(
        s -> {
          var old =
              k.row("SELECT * FROM schedules WHERE id=? AND owner_id=? FOR UPDATE", id, owner);
          if (Set.of("CANCELLED", "COMPLETED").contains(String.valueOf(old.get("status"))))
            throw Kernel.error(409, "SCHEDULE_TERMINAL");
          if (((Number) old.get("revision")).longValue() != rev)
            throw Kernel.error(409, "REVISION_CONFLICT");
          boolean workEdit =
              b.keySet().stream()
                  .anyMatch(
                      Set.of(
                              "title",
                              "instruction",
                              "kind",
                              "timezone",
                              "local_time",
                              "interval_seconds",
                              "first_fire_at")
                          ::contains);
          if (workEdit && !"CHAT".equals(old.get("task_kind")))
            throw Kernel.error(400, "MANAGED_SCHEDULE");
          String title =
              b.containsKey("title")
                  ? Kernel.text(b, "title", 200)
                  : String.valueOf(old.get("title"));
          String instruction =
              b.containsKey("instruction")
                  ? Kernel.text(b, "instruction", 16000)
                  : String.valueOf(old.get("instruction"));
          String kind =
              b.containsKey("kind") ? Kernel.text(b, "kind", 20) : String.valueOf(old.get("kind"));
          String zone =
              b.containsKey("timezone")
                  ? Kernel.text(b, "timezone", 80)
                  : String.valueOf(old.get("timezone"));
          if (!Set.of("ONCE", "INTERVAL", "DAILY").contains(kind))
            throw Kernel.error(400, "INVALID_SCHEDULE_KIND");
          long rawSeconds =
              kind.equals("INTERVAL")
                  ? (b.containsKey("interval_seconds")
                      ? Kernel.number(b, "interval_seconds")
                      : (old.get("interval_seconds") instanceof Number n ? n.longValue() : 0))
                  : 0;
          if (kind.equals("INTERVAL") && (rawSeconds < 60 || rawSeconds > 31536000))
            throw Kernel.error(400, "INVALID_INTERVAL");
          Integer seconds = kind.equals("INTERVAL") ? (int) rawSeconds : null;
          String local =
              kind.equals("DAILY")
                  ? (b.containsKey("local_time")
                      ? Kernel.text(b, "local_time", 20)
                      : String.valueOf(old.get("local_time")))
                  : null;
          Timestamp next = (Timestamp) old.get("next_fire_at");
          try {
            ZoneId.of(zone);
            LocalTime time = local == null ? null : LocalTime.parse(local);
            if (b.keySet().stream()
                .anyMatch(
                    Set.of("kind", "timezone", "local_time", "interval_seconds", "first_fire_at")
                        ::contains)) {
              Instant now =
                  k.db.queryForObject("SELECT clock_timestamp()", Timestamp.class).toInstant();
              Instant anchor =
                  b.containsKey("first_fire_at")
                      ? Instant.parse(Kernel.text(b, "first_fire_at", 80))
                      : kind.equals("ONCE")
                          ? (next == null ? now.minusSeconds(60) : next.toInstant())
                          : kind.equals("INTERVAL") ? now.plusSeconds(seconds) : now;
              if (anchor.isBefore(now.minusSeconds(5))) throw Kernel.error(400, "SCHEDULE_IN_PAST");
              next =
                  Timestamp.from(
                      kind.equals("DAILY")
                          ? ScheduleTime.nextDaily(anchor.minusNanos(1), zone, time)
                          : anchor);
            }
          } catch (DateTimeException invalid) {
            throw Kernel.error(400, "INVALID_SCHEDULE_TIME");
          }
          var request =
              new LinkedHashMap<String, Object>(k.decode(String.valueOf(old.get("task_request"))));
          if (b.containsKey("notification_policy")) {
            // Replace only the notification rule; preserve capability-specific task inputs.
            request.remove("notification_policy");
            request.remove("notification_condition");
            var ruleBody = new LinkedHashMap<String, Object>(b);
            ruleBody.put("task_request", request);
            request = new LinkedHashMap<>(NotificationRules.request(ruleBody));
          }
          k.db.update(
              // The Schedule lock serializes edits with occurrence claiming. Existing Runs stay
              // frozen.
              "UPDATE schedules SET status=?,task_request=?::jsonb,title=?,instruction=?,kind=?,timezone=?,local_time=?::time,interval_seconds=?,next_fire_at=?,revision=revision+1 WHERE id=?",
              status == null ? old.get("status") : status,
              k.encode(request),
              title,
              instruction,
              kind,
              zone,
              local,
              seconds,
              next,
              id);
          return k.row("SELECT * FROM schedules WHERE id=?", id);
        });
  }

  public Object delete(Map<String, Object> claims, UUID id, long revision) {
    UUID owner = Kernel.uuid(claims.get("owner"));
    return k.tx.execute(
        tx -> {
          var found =
              k.db.queryForList(
                  "SELECT idempotency_key FROM schedules WHERE id=? AND owner_id=?", id, owner);
          if (found.isEmpty()) {
            if (k.db.queryForObject(
                    "SELECT count(*) FROM deleted_schedules WHERE id=? AND owner_id=?",
                    Integer.class,
                    id,
                    owner)
                == 0) throw Kernel.error(404, "NOT_FOUND");
            return Map.of("ok", true, "id", id);
          }
          String key = String.valueOf(found.getFirst().get("idempotency_key"));
          // Serialize create retries before locking schedule, matching create's lock order.
          k.db.queryForObject(
              "SELECT pg_advisory_xact_lock(hashtextextended(?,0))",
              Object.class,
              owner + ":" + key);
          var rows =
              k.db.queryForList(
                  "SELECT * FROM schedules WHERE id=? AND owner_id=? FOR UPDATE", id, owner);
          if (rows.isEmpty())
            return Map.of("ok", true, "id", id); // Concurrent owned delete committed.
          var schedule = rows.getFirst();
          if (((Number) schedule.get("revision")).longValue() != revision)
            throw Kernel.error(409, "REVISION_CONFLICT");
          // Schedule -> Run -> attempt. Epoch invalidation rejects late checkpoint/result commits.
          var active =
              k.db.queryForList(
                  "SELECT id,attempt_id FROM runs WHERE schedule_id=? AND status NOT IN ('COMPLETED','FAILED','CANCELLED','UNKNOWN') ORDER BY id FOR UPDATE",
                  id);
          for (var run : active) {
            k.db.update(
                "UPDATE runs SET status='CANCELLED',epoch=epoch+1,lease_until=NULL,updated_at=now() WHERE id=?",
                run.get("id"));
            k.db.update(
                "UPDATE attempts SET status='CANCELLED',ended_at=now() WHERE id=?",
                run.get("attempt_id"));
          }
          k.db.update(
              "INSERT INTO deleted_schedules(id,owner_id,idempotency_key) VALUES(?,?,?)",
              id,
              owner,
              key);
          k.db.update("DELETE FROM schedules WHERE id=? AND owner_id=?", id, owner);
          return Map.of("ok", true, "id", id);
        });
  }
}
