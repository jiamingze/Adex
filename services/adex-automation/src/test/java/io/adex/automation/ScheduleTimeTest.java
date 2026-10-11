package io.adex.automation;

import static org.junit.jupiter.api.Assertions.*;

import io.adex.automation.schedule.ScheduleTime;
import java.time.*;
import org.junit.jupiter.api.Test;

class ScheduleTimeTest {
  @Test
  void dailyShanghai() {
    assertEquals(
        Instant.parse("2026-10-11T00:00:00Z"),
        ScheduleTime.nextDaily(
            Instant.parse("2026-10-10T00:00:00Z"), "Asia/Shanghai", LocalTime.of(8, 0)));
  }

  @Test
  void springGap() {
    assertEquals(
        Instant.parse("2026-03-08T07:30:00Z"),
        ScheduleTime.nextDaily(
            Instant.parse("2026-03-08T00:00:00Z"), "America/New_York", LocalTime.of(2, 30)));
  }

  @Test
  void fallOverlapOnlyOnce() {
    assertEquals(
        Instant.parse("2026-11-02T06:30:00Z"),
        ScheduleTime.nextDaily(
            Instant.parse("2026-11-01T05:30:00Z"), "America/New_York", LocalTime.of(1, 30)));
  }

  @Test
  void missedIntervalCoalesces() {
    assertEquals(
        Instant.parse("2026-10-10T00:11:00Z"),
        ScheduleTime.nextInterval(
            Instant.parse("2026-10-10T00:00:00Z"), Instant.parse("2026-10-10T00:10:30Z"), 60));
  }
}
