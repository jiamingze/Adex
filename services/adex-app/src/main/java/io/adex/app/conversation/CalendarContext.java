package io.adex.app.conversation;

import io.adex.kernel.Kernel;
import java.time.Instant;
import java.time.ZoneId;
import java.util.*;

/** Validates an untrusted native calendar observation; it grants no write permission. */
public final class CalendarContext {
  private CalendarContext() {}

  public static Map<String, Object> normalize(Object raw) {
    if (raw == null) return null;
    try {
      if (!(raw instanceof Map<?, ?> value)
          || !Set.of("source", "observed_at", "timezone", "partial", "events")
              .equals(value.keySet())
          || !"device".equals(value.get("source"))
          || !(value.get("partial") instanceof Boolean)
          || !(value.get("events") instanceof List<?> events)
          || events.size() > 40) throw new IllegalArgumentException();
      var observed = Instant.parse(String.valueOf(value.get("observed_at")));
      if (observed.isAfter(Instant.now().plusSeconds(60))) throw new IllegalArgumentException();
      String timezone = String.valueOf(value.get("timezone"));
      ZoneId.of(timezone);
      var normalized = new ArrayList<Object>();
      for (Object item : events) {
        if (!(item instanceof Map<?, ?> event)
            || !Set.of("title", "start", "end", "all_day", "location", "organizer")
                .equals(event.keySet())
            || !(event.get("all_day") instanceof Boolean)) throw new IllegalArgumentException();
        var start = Instant.parse(String.valueOf(event.get("start")));
        var end = Instant.parse(String.valueOf(event.get("end")));
        if (!end.isAfter(start)) throw new IllegalArgumentException();
        normalized.add(
            Map.of(
                "title",
                text(event, "title", 200),
                "start",
                start.toString(),
                "end",
                end.toString(),
                "all_day",
                event.get("all_day"),
                "location",
                text(event, "location", 300),
                "organizer",
                text(event, "organizer", 200)));
      }
      return Map.of(
          "source",
          "device",
          "observed_at",
          observed.toString(),
          "timezone",
          timezone,
          "partial",
          value.get("partial"),
          "events",
          normalized);
    } catch (Exception invalid) {
      throw Kernel.error(400, "INVALID_CLIENT_CALENDAR");
    }
  }

  private static String text(Map<?, ?> value, String key, int max) {
    if (!(value.get(key) instanceof String text) || text.length() > max)
      throw new IllegalArgumentException();
    return text;
  }
}
