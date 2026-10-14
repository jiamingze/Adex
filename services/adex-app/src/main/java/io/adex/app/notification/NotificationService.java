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
            "SELECT n.* FROM notifications n WHERE n.owner_id=? AND (n.conversation_id IS NULL OR EXISTS (SELECT 1 FROM conversations c WHERE c.id=n.conversation_id AND c.owner_id=n.owner_id AND c.deleted_at IS NULL)) ORDER BY n.created_at DESC LIMIT 100",
            owner));
  }

  public Object resume(UUID owner, UUID id) {
    var item = k.row("SELECT * FROM notifications WHERE id=? AND owner_id=?", id, owner);
    k.row(
        "SELECT id FROM conversations WHERE id=? AND owner_id=? AND deleted_at IS NULL",
        item.get("conversation_id"),
        owner);
    var result = new LinkedHashMap<String, Object>();
    result.put("conversation_id", item.get("conversation_id"));
    result.put("action_id", item.get("action_id"));
    if (item.get("run_id") != null)
      result.put(
          "run",
          k.call(
              "automation",
              "run:read",
              owner,
              Kernel.uuid(item.get("run_id")),
              "GET",
              "/internal/runs/" + item.get("run_id"),
              null));
    k.db.update("UPDATE notifications SET read=true WHERE id=? AND owner_id=?", id, owner);
    return result;
  }

  public Object read(UUID owner, UUID id) {
    if (k.db.update("UPDATE notifications SET read=true WHERE id=? AND owner_id=?", id, owner) != 1)
      throw Kernel.error(404, "NOT_FOUND");
    return Map.of("ok", true);
  }
}
