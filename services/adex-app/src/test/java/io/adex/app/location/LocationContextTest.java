package io.adex.app.location;

import static org.junit.jupiter.api.Assertions.*;

import java.time.Instant;
import java.util.Map;
import org.junit.jupiter.api.Test;

class LocationContextTest {
  @Test
  void coarseDeviceCoordinatesAndManualCity() {
    var device =
        LocationContext.normalize(
            Map.of(
                "source",
                "device",
                "label",
                "TEST_FIXTURE city",
                "latitude",
                31.234567,
                "longitude",
                121.47891,
                "observed_at",
                Instant.now().toString()));
    assertEquals(31.23, device.get("latitude"));
    assertEquals(121.48, device.get("longitude"));
    assertFalse(
        LocationContext.normalize(
                Map.of("source", "manual", "label", "上海", "observed_at", Instant.now().toString()))
            .containsKey("latitude"));
  }

  @Test
  void invalidOrUnconsentedMetadataFailsClosed() {
    for (var raw :
        java.util.List.of(
            Map.of("source", "ip", "label", "上海", "observed_at", Instant.now().toString()),
            Map.of(
                "source",
                "device",
                "label",
                "",
                "latitude",
                Double.NaN,
                "longitude",
                1,
                "observed_at",
                Instant.now().toString()),
            Map.of("source", "manual", "label", "", "observed_at", Instant.now().toString()),
            Map.of(
                "source",
                "manual",
                "label",
                "上海",
                "observed_at",
                Instant.now().plusSeconds(3600).toString())))
      assertThrows(RuntimeException.class, () -> LocationContext.normalize(raw));
  }
}
