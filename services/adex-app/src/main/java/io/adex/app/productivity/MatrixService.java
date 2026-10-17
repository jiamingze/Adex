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
    String description = b.containsKey("description") ? String.valueOf(b.get("description")) : null;
    if (description != null && description.length() > 16000)
      throw Kernel.error(400, "INVALID_MATRIX_TASK");
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
          "INSERT INTO matrix_tasks(id,owner_id,title,important,urgent,due_at,status,run_id,conversation_id,description) VALUES(?,?,?,?,?,?,?,?,?,?) RETURNING *",
          Kernel.id(),
          owner,
          title,
          b.get("important"),
          b.get("urgent"),
          due,
          status,
          run,
          conv,
          description == null ? "" : description);
    var rows =
        k.db.queryForList(
            "UPDATE matrix_tasks SET title=?,important=?,urgent=?,due_at=?,status=?,run_id=?,conversation_id=?,description=COALESCE(?,description),revision=revision+1 WHERE id=? AND owner_id=? AND revision=? RETURNING *",
            title,
            b.get("important"),
            b.get("urgent"),
            due,
            status,
            run,
            conv,
            description,
            id,
            owner,
            Kernel.number(b, "revision"));
    if (rows.isEmpty()) throw Kernel.error(409, "REVISION_CONFLICT");
    return rows.getFirst();
  }

  /** Serialize against turn takeover/cancel; commit todo before issuing a success receipt. */
  public Map<String, Object> fromChat(
      UUID owner, UUID conv, Map<String, Object> turn, Map<String, Object> draft) {
    return k.tx.execute(
        tx -> {
          // Match chat commit lock order: conversation, then turn, then local task.
          // No LLM or remote call under these short transaction locks.
          k.row(
              "SELECT id FROM conversations WHERE id=? AND owner_id=? AND deleted_at IS NULL FOR UPDATE",
              conv,
              owner);
          k.row(
              "SELECT id FROM turns WHERE id=? AND owner_id=? AND epoch=? AND attempt_id=? AND status='RUNNING' AND lease_until>clock_timestamp() FOR UPDATE",
              turn.get("id"),
              owner,
              turn.get("epoch"),
              turn.get("attempt_id"));
          var existing =
              k.db.queryForList(
                  "SELECT * FROM matrix_tasks WHERE source_turn_id=? AND owner_id=?",
                  turn.get("id"),
                  owner);
          if (!existing.isEmpty()) return existing.getFirst();
          var body = new LinkedHashMap<String, Object>();
          for (String key : List.of("title", "important", "urgent", "due_at", "description"))
            body.put(key, draft.get(key));
          if (body.get("important") == null) body.put("important", true);
          if (body.get("urgent") == null) body.put("urgent", false);
          if (body.get("description") == null) body.put("description", "");
          if (body.get("due_at") == null) {
            var created =
                k.db.queryForObject(
                    "SELECT created_at FROM turns WHERE id=?",
                    java.sql.Timestamp.class,
                    turn.get("id"));
            body.put("due_at", created.toInstant().plus(java.time.Duration.ofDays(1)).toString());
          }
          body.put("conversation_id", conv);
          @SuppressWarnings("unchecked")
          var saved = (Map<String, Object>) save(owner, null, body);
          k.db.update(
              "UPDATE matrix_tasks SET source_turn_id=? WHERE id=?",
              turn.get("id"),
              saved.get("id"));
          return saved;
        });
  }

  public String chatReceipt(Map<String, Object> saved) {
    String due =
        saved.get("due_at") == null
            ? "未设置"
            : (saved.get("due_at") instanceof OffsetDateTime value
                    ? value
                    : ((java.sql.Timestamp) saved.get("due_at"))
                        .toInstant()
                        .atOffset(java.time.ZoneOffset.UTC))
                .atZoneSameInstant(java.time.ZoneId.of("Asia/Shanghai"))
                .format(java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm（北京时间）"));
    String description = String.valueOf(saved.getOrDefault("description", ""));
    return "已添加到你的待办\n\n- **任务**："
        + saved.get("title")
        + (description.isBlank() ? "" : "\n- **详情**：" + description)
        + "\n- **截止时间**："
        + due
        + "\n- **重要程度**："
        + (Boolean.TRUE.equals(saved.get("important")) ? "重要" : "不重要")
        + "\n- **紧急程度**："
        + (Boolean.TRUE.equals(saved.get("urgent")) ? "紧急" : "不紧急")
        + "\n- **状态**：待处理\n\n可在待办页查看和完成。";
  }

  public Object delete(UUID owner, UUID id) {
    if (k.db.update("DELETE FROM matrix_tasks WHERE id=? AND owner_id=?", id, owner) != 1)
      throw Kernel.error(404, "NOT_FOUND");
    return Map.of("ok", true);
  }
}
