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
    if (!Set.of("DAILY", "ONCE", "INTERVAL").contains(kind))
      throw Kernel.error(400, "INVALID_SCHEDULE_KIND");
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
    } else if (kind.equals("INTERVAL")) {
      if (!(draft.get("interval_seconds") instanceof Number interval)
          || interval.longValue() < 60
          || interval.longValue() > 31536000) throw Kernel.error(400, "INVALID_INTERVAL");
      request.put("interval_seconds", interval.longValue());
      first = created.plusSeconds(interval.longValue());
      timing = "每 " + interval.longValue() / 60 + " 分钟";
    } else if (draft.get("first_fire_at") instanceof String absolute) {
      first = OffsetDateTime.parse(absolute).toInstant();
      timing =
          first.atZone(zone).format(java.time.format.DateTimeFormatter.ofPattern("MM-dd HH:mm:ss"));
    } else {
      if (!(draft.get("delay_seconds") instanceof Number delay)
          || delay.longValue() < 1
          || delay.longValue() > 31536000) throw Kernel.error(400, "INVALID_INTERVAL");
      // Retries use the original turn time so the schedule's request hash stays stable.
      first = created.plusSeconds(delay.longValue());
      timing =
          first.atZone(zone).format(java.time.format.DateTimeFormatter.ofPattern("MM-dd HH:mm:ss"));
    }
    String policy = String.valueOf(draft.getOrDefault("notification_policy", null));
    if (policy.equals("null")) policy = "EVERY_RUN";
    // Keep legacy default payloads stable for retries across deployment boundaries.
    if (kind.equals("INTERVAL") && !policy.equals("CONDITION_MET"))
      request.put("task_request", Map.of("notification_policy", policy));
    else if (!policy.equals("EVERY_RUN")) request.put("notification_policy", policy);
    if (draft.get("notification_condition") != null)
      request.put("notification_condition", draft.get("notification_condition"));
    request.put("first_fire_at", first.toString());
    request.put("origin_conversation_id", conv);
    request.put("idempotency_key", "chat-schedule:" + turn);
    var schedule =
        k.call(
            "automation", "schedule:write", owner, null, "POST", "/internal/automations", request);
    if (schedule.get("id") == null || !"ACTIVE".equals(schedule.get("status")))
      throw Kernel.error(502, "SCHEDULE_RECEIPT_MISSING");
    @SuppressWarnings("unchecked")
    var owned =
        (List<Map<String, Object>>)
            k.call("automation", "schedule:read", owner, null, "GET", "/internal/automations", null)
                .get("items");
    var observed =
        owned.stream()
            .filter(row -> String.valueOf(schedule.get("id")).equals(String.valueOf(row.get("id"))))
            .findFirst()
            .orElseThrow(() -> Kernel.error(502, "TASK_READBACK_MISSING"));
    for (String field : List.of("title", "instruction", "kind", "timezone"))
      if (!String.valueOf(request.get(field)).equals(String.valueOf(observed.get(field))))
        throw Kernel.error(502, "TASK_READBACK_MISMATCH");
    return Map.of(
        "content",
        "已设置"
            + timing
            + "（"
            + zone
            + "）执行："
            + request.get("instruction")
            + (policy.equals("CONDITION_MET")
                ? "。通知条件："
                    + ((Map<?, ?>) request.get("notification_condition")).get("description")
                    + "。仅满足条件时通知；不满足或无法核实时只记录到当前会话，不发通知。"
                : "。结果会回到当前对话，并按通知设置推送。"),
        "card",
        Map.of(
            "type",
            "automation_status",
            "data",
            Map.of(
                "notification_policy",
                policy,
                "notification_condition",
                request.getOrDefault("notification_condition", Map.of()),
                "schedule_id",
                schedule.get("id"),
                "interval_seconds",
                request.getOrDefault("interval_seconds", 0),
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
