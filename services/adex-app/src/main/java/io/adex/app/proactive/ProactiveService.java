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

  public Object list(UUID owner) {
    return Kernel.items(
        k.db.queryForList(
            "SELECT * FROM proactive_signals WHERE owner_id=? ORDER BY created_at DESC LIMIT 100",
            owner));
  }
}
