package io.adex.app.integration;

import io.adex.kernel.Kernel;
import java.time.*;
import java.util.*;
import org.springframework.stereotype.Service;

/** Translates chat timing proposals into the existing Automation schedule contract. */
@Service
public class ChatScheduleService {
  private final Kernel k;

  public ChatScheduleService(Kernel k) {
    this.k = k;
  }

  public Map<String, Object> create(UUID owner, UUID conv, UUID turn, Map<?, ?> draft) {
    String kind = String.valueOf(draft.get("kind"));
    if (!Set.of("DAILY", "ONCE").contains(kind)) throw Kernel.error(400, "INVALID_SCHEDULE_KIND");
    var zone = ZoneId.of(String.valueOf(draft.get("timezone")));
    var created =
        k.db
            .queryForObject(
                "SELECT created_at FROM turns WHERE id=? AND owner_id=?",
                java.sql.Timestamp.class,
                turn,
                owner)
            .toInstant();
    var request = new LinkedHashMap<String, Object>();
    for (String field : List.of("title", "instruction", "kind", "timezone"))
      request.put(field, draft.get(field));
    Instant first;
    String timing;
    if (kind.equals("DAILY")) {
      var time = LocalTime.parse(String.valueOf(draft.get("local_time")));
      var local = created.atZone(zone);
      var next = local.toLocalDate().atTime(time).atZone(zone);
      if (!next.isAfter(local)) next = next.plusDays(1);
      first = next.toInstant();
      request.put("local_time", time.toString());
      timing = "每天 " + time;
    } else {
      if (!(draft.get("delay_seconds") instanceof Number delay)
          || delay.longValue() < 1
          || delay.longValue() > 31536000) throw Kernel.error(400, "INVALID_INTERVAL");
      // Retries use the original turn time so the schedule's request hash stays stable.
      first = created.plusSeconds(delay.longValue());
      timing =
          first.atZone(zone).format(java.time.format.DateTimeFormatter.ofPattern("MM-dd HH:mm:ss"));
    }
    request.put("first_fire_at", first.toString());
    request.put("origin_conversation_id", conv);
    request.put("idempotency_key", "chat-schedule:" + turn);
    var schedule =
        k.call(
            "automation", "schedule:write", owner, null, "POST", "/internal/automations", request);
    return Map.of(
        "content",
        "已设置" + timing + "（" + zone + "）执行：" + request.get("instruction") + "。结果会回到当前对话，并按通知设置推送。",
        "card",
        Map.of(
            "type",
            "automation_status",
            "data",
            Map.of(
                "schedule_id",
                schedule.get("id"),
                "kind",
                kind,
                "local_time",
                String.valueOf(request.getOrDefault("local_time", "")),
                "first_fire_at",
                first.toString(),
                "timezone",
                zone.toString(),
                "status",
                schedule.get("status")),
            "actions",
            List.of("open_tasks")));
  }
}
