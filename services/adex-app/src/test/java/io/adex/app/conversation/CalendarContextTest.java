package io.adex.app.conversation;

import static org.junit.jupiter.api.Assertions.*;

import java.time.Instant;
import java.util.*;
import org.junit.jupiter.api.Test;

class CalendarContextTest {
  Map<String, Object> snapshot(List<?> events) {
    return Map.of(
        "source",
        "device",
        "observed_at",
        Instant.now().toString(),
        "timezone",
        "Asia/Shanghai",
        "partial",
        false,
        "events",
        events);
  }

  @Test
  void boundedObservationDoesNotGrantWrites() {
    var event =
        Map.of(
            "title",
            "TEST_FIXTURE",
            "start",
            "2026-10-20T00:00:00Z",
            "end",
            "2026-10-20T01:00:00Z",
            "all_day",
            false,
            "location",
            "",
            "organizer",
            "");
    assertEquals(
        1, ((List<?>) CalendarContext.normalize(snapshot(List.of(event))).get("events")).size());
    assertThrows(
        RuntimeException.class,
        () -> CalendarContext.normalize(snapshot(Collections.nCopies(41, event))));
    var bad = new HashMap<String, Object>(event);
    bad.put("password", "secret");
    assertThrows(RuntimeException.class, () -> CalendarContext.normalize(snapshot(List.of(bad))));
    final var invalid = new HashMap<String, Object>(event);
    invalid.put("end", event.get("start"));
    assertThrows(
        RuntimeException.class, () -> CalendarContext.normalize(snapshot(List.of(invalid))));
  }
}
