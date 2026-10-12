package io.adex.app.notification;

import io.adex.kernel.Kernel;
import java.time.*;
import java.util.*;
import org.springframework.stereotype.Service;

@Service
public class NotificationPreferences {
  private final Kernel k;

  public NotificationPreferences(Kernel k) {
    this.k = k;
  }

  public Map<String, Object> get(UUID owner) {
    k.db.update(
        "INSERT INTO notification_preferences(owner_id) VALUES(?) ON CONFLICT DO NOTHING", owner);
    return k.row("SELECT * FROM notification_preferences WHERE owner_id=?", owner);
  }

  public Object save(UUID owner, Map<String, Object> b) {
    if (!(b.get("enabled") instanceof Boolean) || !(b.get("push_enabled") instanceof Boolean))
      throw Kernel.error(400, "INVALID_NOTIFICATION_PREFERENCES");
    long min = Kernel.number(b, "min_importance");
    if (min < 0 || min > 100) throw Kernel.error(400, "INVALID_IMPORTANCE");
    String tz = Kernel.text(b, "timezone", 80);
    LocalTime start = null, end = null;
    try {
      ZoneId.of(tz);
      if (!ZoneId.getAvailableZoneIds().contains(tz)) throw new IllegalArgumentException();
      if (b.get("quiet_start") != null && !b.get("quiet_start").toString().isBlank())
        start = LocalTime.parse(b.get("quiet_start").toString());
      if (b.get("quiet_end") != null && !b.get("quiet_end").toString().isBlank())
        end = LocalTime.parse(b.get("quiet_end").toString());
      if ((start == null) != (end == null) || (start != null && start.equals(end)))
        throw new IllegalArgumentException();
    } catch (Exception e) {
      throw Kernel.error(400, "INVALID_QUIET_HOURS");
    }
    k.db.update(
        "INSERT INTO notification_preferences(owner_id,enabled,push_enabled,min_importance,quiet_start,quiet_end,timezone) VALUES(?,?,?,?,?,?,?) ON CONFLICT(owner_id) DO UPDATE SET enabled=excluded.enabled,push_enabled=excluded.push_enabled,min_importance=excluded.min_importance,quiet_start=excluded.quiet_start,quiet_end=excluded.quiet_end,timezone=excluded.timezone",
        owner,
        b.get("enabled"),
        b.get("push_enabled"),
        min,
        start,
        end,
        tz);
    return get(owner);
  }

  public static boolean quiet(String start, String end, String zone, Instant now) {
    if (start == null || end == null) return false;
    LocalTime time = now.atZone(ZoneId.of(zone)).toLocalTime(),
        a = LocalTime.parse(start),
        b = LocalTime.parse(end);
    return a.isBefore(b)
        ? !time.isBefore(a) && time.isBefore(b)
        : !time.isBefore(a) || time.isBefore(b);
  }
}
