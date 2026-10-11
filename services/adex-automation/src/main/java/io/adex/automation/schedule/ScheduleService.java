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
            "SELECT * FROM schedules WHERE owner_id=? ORDER BY created_at DESC LIMIT 100",
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
    String hash = Kernel.hash(k.encode(new TreeMap<>(b)));
    return k.tx.execute(
        s -> {
          // Serialize owner+key only, independent of schedulers and other owners.
          k.db.queryForObject(
              "SELECT pg_advisory_xact_lock(hashtextextended(?,0))",
              Object.class,
              owner + ":" + key);
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
          if (first.isBefore(now.minusSeconds(5))) throw Kernel.error(400, "SCHEDULE_IN_PAST");
          if (k.db.queryForObject(
                  "SELECT count(*) FROM schedules WHERE owner_id=? AND status IN"
                      + " ('ACTIVE','PAUSED')",
                  Integer.class,
                  owner)
              >= 100) throw Kernel.error(429, "SCHEDULE_LIMIT");
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
          return k.row("SELECT * FROM schedules WHERE id=?", id);
        });
  }

  public Object update(Map<String, Object> claims, UUID id, Map<String, Object> b) {
    UUID owner = Kernel.uuid(claims.get("owner"));
    String status = Kernel.text(b, "status", 20);
    if (!Set.of("ACTIVE", "PAUSED", "CANCELLED").contains(status))
      throw Kernel.error(400, "INVALID_STATUS");
    long rev = Kernel.number(b, "revision");
    return k.tx.execute(
        s -> {
          var old =
              k.row("SELECT * FROM schedules WHERE id=? AND owner_id=? FOR UPDATE", id, owner);
          if (Set.of("CANCELLED", "COMPLETED").contains(String.valueOf(old.get("status"))))
            throw Kernel.error(409, "SCHEDULE_TERMINAL");
          if (((Number) old.get("revision")).longValue() != rev)
            throw Kernel.error(409, "REVISION_CONFLICT");
          k.db.update("UPDATE schedules SET status=?,revision=revision+1 WHERE id=?", status, id);
          return k.row("SELECT * FROM schedules WHERE id=?", id);
        });
  }
}
