package io.adex.automation.schedule;

import java.time.*;

public final class ScheduleTime {
  private ScheduleTime() {}

  public static Instant nextDaily(Instant after, String timezone, LocalTime time) {
    ZoneId zone = ZoneId.of(timezone);
    LocalDate date = after.atZone(zone).toLocalDate();
    Instant next = date.atTime(time).atZone(zone).toInstant();
    if (!next.isAfter(after)) next = date.plusDays(1).atTime(time).atZone(zone).toInstant();
    return next;
  }

  public static Instant nextInterval(Instant scheduled, Instant now, int seconds) {
    long skips =
        Math.max(1, Math.floorDiv(Duration.between(scheduled, now).getSeconds(), seconds) + 1);
    return scheduled.plusSeconds(Math.multiplyExact(skips, seconds));
  }
}
