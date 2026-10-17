package io.adex.app.location;

import io.adex.kernel.Kernel;
import java.time.Instant;
import java.util.*;

/** Validates optional, consented per-turn location; never guesses a user's city. */
public final class LocationContext {
  private LocationContext() {}

  public static Map<String, Object> normalize(Object raw) {
    if (raw == null) return null;
    try {
      if (!(raw instanceof Map<?, ?> value)
          || !Set.of("source", "label", "observed_at", "latitude", "longitude")
              .containsAll(value.keySet())) throw new IllegalArgumentException();
      String source = String.valueOf(value.get("source"));
      if (!(value.get("label") instanceof String)) throw new IllegalArgumentException();
      String label = (String) value.get("label");
      Instant observed = Instant.parse(String.valueOf(value.get("observed_at")));
      if (!Set.of("device", "manual").contains(source)
          || label.equals("null")
          || label.length() > 120
          || observed.isAfter(Instant.now().plusSeconds(60))) throw new IllegalArgumentException();
      var result = new LinkedHashMap<String, Object>();
      result.put("source", source);
      result.put("label", label.strip());
      result.put("observed_at", observed.toString());
      if (source.equals("device")) {
        double lat = ((Number) value.get("latitude")).doubleValue();
        double lon = ((Number) value.get("longitude")).doubleValue();
        if (!Double.isFinite(lat)
            || !Double.isFinite(lon)
            || Math.abs(lat) > 90
            || Math.abs(lon) > 180) throw new IllegalArgumentException();
        result.put("latitude", Math.round(lat * 100.0) / 100.0);
        result.put("longitude", Math.round(lon * 100.0) / 100.0);
      } else if (label.isBlank() || value.containsKey("latitude") || value.containsKey("longitude"))
        throw new IllegalArgumentException();
      return result;
    } catch (Exception error) {
      throw Kernel.error(400, "INVALID_CLIENT_LOCATION");
    }
  }
}
