package io.adex.app.productivity;

import io.adex.app.conversation.ConversationStore;
import io.adex.kernel.Kernel;
import java.time.OffsetDateTime;
import java.util.*;
import org.springframework.stereotype.Service;

/** User task organization only; linking a Run never creates another execution system. */
@Service
public class MatrixService {
  private final Kernel k;
  private final ConversationStore chat;

  public MatrixService(Kernel k, ConversationStore chat) {
    this.k = k;
    this.chat = chat;
  }

  public Object list(UUID owner) {
    return Kernel.items(
        k.db.queryForList(
            "SELECT *,CASE WHEN important AND urgent THEN 'DO' WHEN important THEN 'PLAN' WHEN urgent THEN 'DELEGATE' ELSE 'ELIMINATE' END AS quadrant FROM matrix_tasks WHERE owner_id=? ORDER BY status,created_at DESC LIMIT 500",
            owner));
  }

  public Object save(UUID owner, UUID id, Map<String, Object> b) {
    String title = Kernel.text(b, "title", 200),
        status = String.valueOf(b.getOrDefault("status", "TODO"));
    if (!(b.get("important") instanceof Boolean)
        || !(b.get("urgent") instanceof Boolean)
        || !Set.of("TODO", "DONE").contains(status)) throw Kernel.error(400, "INVALID_MATRIX_TASK");
    OffsetDateTime due = null;
    try {
      if (b.get("due_at") != null && !String.valueOf(b.get("due_at")).isBlank())
        due = OffsetDateTime.parse(String.valueOf(b.get("due_at")));
    } catch (Exception e) {
      throw Kernel.error(400, "INVALID_DUE_DATE");
    }
    UUID conv = b.get("conversation_id") == null ? null : Kernel.uuid(b.get("conversation_id"));
    UUID run = b.get("run_id") == null ? null : Kernel.uuid(b.get("run_id"));
    if (conv != null) chat.own(owner, conv);
    if (run != null)
      k.call("automation", "run:read", owner, run, "GET", "/internal/runs/" + run, null);
    if (id == null)
      return k.row(
          "INSERT INTO matrix_tasks(id,owner_id,title,important,urgent,due_at,status,run_id,conversation_id) VALUES(?,?,?,?,?,?,?,?,?) RETURNING *",
          Kernel.id(),
          owner,
          title,
          b.get("important"),
          b.get("urgent"),
          due,
          status,
          run,
          conv);
    var rows =
        k.db.queryForList(
            "UPDATE matrix_tasks SET title=?,important=?,urgent=?,due_at=?,status=?,run_id=?,conversation_id=?,revision=revision+1 WHERE id=? AND owner_id=? AND revision=? RETURNING *",
            title,
            b.get("important"),
            b.get("urgent"),
            due,
            status,
            run,
            conv,
            id,
            owner,
            Kernel.number(b, "revision"));
    if (rows.isEmpty()) throw Kernel.error(409, "REVISION_CONFLICT");
    return rows.getFirst();
  }

  public Object delete(UUID owner, UUID id) {
    if (k.db.update("DELETE FROM matrix_tasks WHERE id=? AND owner_id=?", id, owner) != 1)
      throw Kernel.error(404, "NOT_FOUND");
    return Map.of("ok", true);
  }
}
