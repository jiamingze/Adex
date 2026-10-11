package io.adex.app.notification;

import io.adex.kernel.Kernel;
import java.util.*;
import org.springframework.stereotype.Service;

/** Owns Notification use cases; HTTP authentication is performed by the adapter. */
@Service
public class NotificationService {
  private final Kernel k;

  public NotificationService(Kernel k) {
    this.k = k;
  }

  public Object notifications(UUID owner) {
    return Kernel.items(
        k.db.queryForList(
            "SELECT * FROM notifications WHERE owner_id=? ORDER BY created_at DESC LIMIT 100",
            owner));
  }

  public Object read(UUID owner, UUID id) {
    if (k.db.update("UPDATE notifications SET read=true WHERE id=? AND owner_id=?", id, owner) != 1)
      throw Kernel.error(404, "NOT_FOUND");
    return Map.of("ok", true);
  }
}
