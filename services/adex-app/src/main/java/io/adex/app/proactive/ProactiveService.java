package io.adex.app.proactive;

import io.adex.kernel.Kernel;
import java.util.*;
import org.springframework.stereotype.Service;

/** Consumes provider observations inside the existing App result transaction. */
@Service
public class ProactiveService {
  private final Kernel k;

  public ProactiveService(Kernel k) {
    this.k = k;
  }

  public int ingest(UUID owner, UUID conv, UUID run, List<?> signals) {
    int count = 0;
    for (Object raw : signals.stream().limit(100).toList()) {
      if (!(raw instanceof Map<?, ?> s)) throw Kernel.error(400, "INVALID_SIGNAL");
      String kind = String.valueOf(s.get("kind"));
      int importance =
          switch (kind) {
            case "CALENDAR_CONFLICT" -> 95;
            case "IMPORTANT_EMAIL" -> 80;
            default -> throw Kernel.error(400, "INVALID_SIGNAL_KIND");
          };
      UUID id = Kernel.id();
      int inserted =
          k.db.update(
              "INSERT INTO proactive_signals(id,owner_id,connection_id,conversation_id,run_id,resource_id,resource_version,kind,correlation_key,importance,reasons,suggestion,evidence) VALUES(?,?,?,?,?,?,?,?,?,?,?::jsonb,?,?::jsonb) ON CONFLICT DO NOTHING",
              id,
              owner,
              Kernel.uuid(s.get("connection_id")),
              conv,
              run,
              s.get("resource_id"),
              s.get("resource_version"),
              kind,
              s.get("correlation_key"),
              importance,
              k.encode(
                  List.of(
                      kind.equals("CALENDAR_CONFLICT")
                          ? "PROVIDER_EVENTS_OVERLAP"
                          : "PROVIDER_IMPORTANT_LABEL")),
              s.get("suggestion"),
              k.encode(s.get("evidence")));
      if (inserted == 0) continue;
      count++;
      var prefs =
          k.db.queryForList(
              "SELECT enabled,min_importance FROM notification_preferences WHERE owner_id=?",
              owner);
      if (!prefs.isEmpty()
          && (!Boolean.TRUE.equals(prefs.getFirst().get("enabled"))
              || importance < ((Number) prefs.getFirst().get("min_importance")).intValue()))
        continue;
      k.db.update(
          "INSERT INTO notifications(id,event_id,owner_id,conversation_id,run_id,title,body,importance) VALUES(?,?,?,?,?,?,?,?)",
          Kernel.id(),
          id,
          owner,
          conv,
          run,
          kind.equals("CALENDAR_CONFLICT") ? "日历有时间冲突" : "重要邮件有变化",
          s.get("suggestion"),
          importance);
    }
    return count;
  }

  public Object feedback(UUID owner, UUID id, Map<String, Object> b) {
    String status = Kernel.text(b, "status", 20);
    if (!Set.of("OPEN", "RESOLVED", "DISMISSED", "SNOOZED").contains(status))
      throw Kernel.error(400, "INVALID_SIGNAL_STATUS");
    java.time.OffsetDateTime until = null;
    if (status.equals("SNOOZED")) {
      try {
        until = java.time.OffsetDateTime.parse(String.valueOf(b.get("snoozed_until")));
      } catch (Exception e) {
        throw Kernel.error(400, "INVALID_SNOOZE");
      }
      var now = java.time.OffsetDateTime.now();
      if (!until.isAfter(now) || until.isAfter(now.plusDays(30)))
        throw Kernel.error(400, "INVALID_SNOOZE");
    }
    var snoozed = until;
    return k.tx.execute(
        tx -> {
          k.row("SELECT id FROM proactive_signals WHERE id=? AND owner_id=? FOR UPDATE", id, owner);
          if (k.db.update(
                  "UPDATE proactive_signals SET status=?,snoozed_until=?,revision=revision+1 WHERE id=? AND owner_id=? AND revision=?",
                  status,
                  snoozed,
                  id,
                  owner,
                  Kernel.number(b, "revision"))
              != 1) throw Kernel.error(409, "REVISION_CONFLICT");
          if (Set.of("RESOLVED", "DISMISSED").contains(status))
            k.db.update(
                "UPDATE notifications SET read=true WHERE event_id=? AND owner_id=?", id, owner);
          return k.row("SELECT * FROM proactive_signals WHERE id=? AND owner_id=?", id, owner);
        });
  }

  public Object list(UUID owner, boolean includeClosed) {
    return Kernel.items(
        k.db.queryForList(
            "SELECT * FROM proactive_signals WHERE owner_id=? AND (? OR status='OPEN' OR (status='SNOOZED' AND snoozed_until<=clock_timestamp())) ORDER BY importance DESC,created_at DESC LIMIT 100",
            owner,
            includeClosed));
  }
}
