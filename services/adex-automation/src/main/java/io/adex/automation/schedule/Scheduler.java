package io.adex.automation.schedule;

import io.adex.kernel.Kernel;
import java.sql.Timestamp;
import java.time.*;
import java.util.*;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class Scheduler {
  final Kernel k;

  public Scheduler(Kernel k) {
    this.k = k;
  }

  @Scheduled(fixedDelay = 1000)
  public void tick() {
    try {
      k.tx.executeWithoutResult(
          s -> {
            var due =
                k.db.queryForList(
                    "SELECT * FROM schedules WHERE status='ACTIVE' AND"
                        + " next_fire_at<=clock_timestamp() ORDER BY next_fire_at FOR UPDATE SKIP"
                        + " LOCKED LIMIT 20");
            Instant now =
                k.db.queryForObject("SELECT clock_timestamp()", Timestamp.class).toInstant();
            for (var schedule : due) {
              UUID sid = (UUID) schedule.get("id");
              Timestamp at = (Timestamp) schedule.get("next_fire_at");
              boolean overlap =
                  k.db.queryForObject(
                          "SELECT count(*) FROM runs WHERE schedule_id=? AND status IN"
                              + " ('QUEUED','RUNNING','UNKNOWN')",
                          Integer.class,
                          sid)
                      > 0;
              UUID run = overlap ? null : Kernel.id();
              int inserted =
                  k.db.update(
                      "INSERT INTO occurrences(schedule_id,scheduled_at,status) VALUES(?,?,?) ON"
                          + " CONFLICT DO NOTHING",
                      sid,
                      at,
                      overlap ? "SKIPPED_OVERLAP" : "CREATED");
              if (inserted == 1 && !overlap) {
                k.db.update(
                    "INSERT INTO runs(id,schedule_id,owner_id,origin_conversation_id,instruction,kind,request)"
                        + " VALUES(?,?,?,?,?,?,?::jsonb)",
                    run,
                    sid,
                    schedule.get("owner_id"),
                    schedule.get("origin_conversation_id"),
                    schedule.get("instruction"),
                    schedule.get("task_kind"),
                    k.encode(schedule.get("task_request")));
                k.db.update(
                    "UPDATE occurrences SET run_id=? WHERE schedule_id=? AND scheduled_at=?",
                    run,
                    sid,
                    at);
              }
              String kind = String.valueOf(schedule.get("kind"));
              Instant next =
                  kind.equals("DAILY")
                      ? ScheduleTime.nextDaily(
                          now,
                          String.valueOf(schedule.get("timezone")),
                          ((java.sql.Time) schedule.get("local_time")).toLocalTime())
                      : kind.equals("INTERVAL")
                          ? ScheduleTime.nextInterval(
                              at.toInstant(),
                              now,
                              ((Number) schedule.get("interval_seconds")).intValue())
                          : null;
              k.db.update(
                  "UPDATE schedules SET next_fire_at=?,status=?,revision=revision+1 WHERE id=?",
                  next == null ? null : Timestamp.from(next),
                  next == null ? "COMPLETED" : "ACTIVE",
                  sid);
            }
          });
    } catch (Exception ignored) {
      /* Never advance schedule without PostgreSQL transaction. */
    }
  }

  @Scheduled(fixedDelay = 1500)
  public void publish() {
    try {
      for (int i = 0; i < 10; i++) {
        var event =
            k.tx.execute(
                s -> {
                  var eligible =
                      k.db.queryForList(
                          "SELECT * FROM outbox WHERE delivered_at IS NULL AND"
                              + " next_attempt_at<=clock_timestamp() AND (lease_until IS NULL OR"
                              + " lease_until<clock_timestamp()) ORDER BY next_attempt_at FOR"
                              + " UPDATE SKIP LOCKED LIMIT 1");
                  if (eligible.isEmpty()) return null;
                  UUID claim = Kernel.id();
                  return k.row(
                      "UPDATE outbox SET lease_until=clock_timestamp()+interval '30"
                          + " seconds',claim_id=?,attempts=attempts+1 WHERE id=? RETURNING *",
                      claim,
                      eligible.getFirst().get("id"));
                });
        if (event == null) break;
        try {
          var p = k.decode(String.valueOf(event.get("payload")));
          k.call(
              "app",
              "result:attach",
              p.get("owner_id"),
              p.get("origin_conversation_id"),
              "POST",
              "/internal/results/attach",
              p);
          k.db.update(
              "UPDATE outbox SET delivered_at=now(),lease_until=NULL WHERE id=? AND claim_id=?",
              event.get("id"),
              event.get("claim_id"));
        } catch (Exception e) {
          k.db.update(
              "UPDATE outbox SET"
                  + " lease_until=NULL,next_attempt_at=now()+make_interval(secs=>least(300,5*attempts))"
                  + " WHERE id=? AND claim_id=?",
              event.get("id"),
              event.get("claim_id"));
        }
      }
    } catch (Exception ignored) {
    }
  }
}
