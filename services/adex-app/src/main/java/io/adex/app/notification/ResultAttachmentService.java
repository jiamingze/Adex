package io.adex.app.notification;

import io.adex.app.conversation.ConversationStore;
import io.adex.app.proactive.ProactiveService;
import io.adex.kernel.Kernel;
import java.util.*;
import org.springframework.stereotype.Service;

/**
 * Idempotent result consumer: dedupe, memory revision, artifact and notification share one
 * transaction.
 */
@Service
public class ResultAttachmentService {
  private final Kernel k;
  private final ConversationStore chat;
  private final ProactiveService proactive;

  public ResultAttachmentService(Kernel k, ConversationStore chat, ProactiveService proactive) {
    this.k = k;
    this.chat = chat;
    this.proactive = proactive;
  }

  public Object monitorAttach(Map<String, Object> claims, Map<String, Object> b) {
    UUID owner = Kernel.uuid(b.get("owner_id")),
        conv = Kernel.uuid(b.get("origin_conversation_id")),
        event = Kernel.uuid(b.get("event_id"));

    if (!owner.toString().equals(claims.get("owner"))) throw Kernel.error(403, "SCOPE_DENIED");
    String content = Kernel.text(b, "content", 64000);
    return k.tx.execute(
        s -> {
          k.row("SELECT id FROM users WHERE id=? FOR SHARE", owner);
          var conversation =
              k.row(
                  "SELECT id,deleted_at FROM conversations WHERE id=? AND owner_id=? FOR UPDATE",
                  conv,
                  owner);
          if (k.db.update(
                  "INSERT INTO consumed_events(event_id) VALUES(?) ON CONFLICT DO NOTHING", event)
              == 0) return Map.of("ok", true);
          if (conversation.get("deleted_at") != null)
            return Map.of("ok", true, "discarded", "CONVERSATION_DELETED");
          chat.append(conv, "assistant", content, "monitor:" + event);
          k.db.update(
              "INSERT INTO notifications(id,event_id,owner_id,conversation_id,title,body) VALUES(?,?,?,?,?,?)",
              Kernel.id(),
              event,
              owner,
              conv,
              "监控发现新信息",
              content);
          return Map.of("ok", true);
        });
  }

  public Object attach(Map<String, Object> claims, Map<String, Object> b) {
    UUID owner = Kernel.uuid(b.get("owner_id")),
        conv = Kernel.uuid(b.get("origin_conversation_id")),
        event = Kernel.uuid(b.get("event_id"));

    if (!owner.toString().equals(claims.get("owner"))) throw Kernel.error(403, "SCOPE_DENIED");
    String content = Kernel.text(b, "content", 64000);
    String delivery = String.valueOf(b.getOrDefault("delivery_key", "result"));
    String dedupe =
        "run:"
            + b.get("run_id")
            + (("BROWSER".equals(b.get("kind")) || "COMPUTER".equals(b.get("kind")))
                    && !"result".equals(delivery)
                ? ":" + delivery
                : "");
    return k.tx.execute(
        s -> {
          var u = k.row("SELECT memory_revision FROM users WHERE id=? FOR SHARE", owner);
          var conversation =
              k.row(
                  "SELECT id,deleted_at FROM conversations WHERE id=? AND owner_id=? FOR UPDATE",
                  conv,
                  owner);
          if (k.db.update(
                  "INSERT INTO consumed_events(event_id) VALUES(?) ON CONFLICT DO NOTHING", event)
              == 0) return Map.of("ok", true, "deduplicated", true);
          if (conversation.get("deleted_at") != null)
            return Map.of("ok", true, "discarded", "CONVERSATION_DELETED");
          if ("MATRIX_REMINDER".equals(b.get("kind"))) {
            if (!(b.get("artifact") instanceof Map<?, ?> artifact))
              throw Kernel.error(400, "INVALID_REMINDER");
            var rows =
                k.db.queryForList(
                    "SELECT t.title,t.description,t.due_at,r.id FROM matrix_reminders r JOIN matrix_tasks t ON t.id=r.task_id AND t.owner_id=r.owner_id WHERE r.id=? AND r.owner_id=? AND r.conversation_id=? AND t.important AND t.status='TODO' AND t.due_at=r.due_at AND t.due_at>clock_timestamp() AND t.due_at<=clock_timestamp()+interval '10 minutes' FOR SHARE OF t",
                    Kernel.uuid(artifact.get("matrix_reminder_id")),
                    owner,
                    conv);
            if (rows.isEmpty()) return Map.of("ok", true, "discarded", "REMINDER_OBSOLETE");
            var task = rows.getFirst();
            var due =
                ((java.sql.Timestamp) task.get("due_at"))
                    .toInstant()
                    .atZone(java.time.ZoneId.of("Asia/Shanghai"))
                    .format(java.time.format.DateTimeFormatter.ofPattern("MM-dd HH:mm"));
            String reminderText = "重要待办即将到期：" + task.get("title") + "\n截止时间：" + due + "（北京时间）";
            chat.append(conv, "assistant", reminderText, dedupe);
            k.db.update(
                "INSERT INTO notifications(id,event_id,owner_id,conversation_id,run_id,title,body,importance,matrix_reminder_id) VALUES(?,?,?,?,?,?,?,?,?)",
                Kernel.id(),
                event,
                owner,
                conv,
                Kernel.uuid(b.get("run_id")),
                "重要待办即将到期",
                reminderText,
                100,
                task.get("id"));
            return Map.of("ok", true);
          }
          if (((Number) u.get("memory_revision")).longValue()
              != Kernel.number(b, "memory_revision"))
            return Map.of("ok", true, "discarded", "MEMORY_REVISION_CHANGED");
          if (!k.db
              .queryForList(
                  "SELECT id FROM messages WHERE conversation_id=? AND dedupe_key=?", conv, dedupe)
              .isEmpty()) return Map.of("ok", true, "deduplicated", true);
          if ("CONNECTOR_SYNC".equals(b.get("kind"))
              && b.get("artifact") instanceof Map<?, ?> artifact
              && artifact.get("signals") instanceof List<?> signals) {
            int count = proactive.ingest(owner, conv, Kernel.uuid(b.get("run_id")), signals);
            if (count > 0) chat.append(conv, "assistant", content, dedupe);
            return Map.of("ok", true, "signals_created", count);
          }
          String kind = String.valueOf(b.getOrDefault("kind", "CHAT"));
          if (Set.of("RESEARCH", "TRAVEL", "GAME", "DIAGRAM", "IMAGE", "AUDIO", "VIDEO")
              .contains(kind)) {
            UUID artifact = Kernel.id();
            String artifactKind = kind.equals("RESEARCH") ? "REPORT" : kind;
            k.db.update(
                "INSERT INTO artifacts(id,owner_id,kind,title,revision,origin_conversation_id,source_run_id) VALUES(?,?,?,?,1,?,?)",
                artifact,
                owner,
                artifactKind,
                "任务作品 · " + kind,
                conv,
                Kernel.uuid(b.get("run_id")));
            Map<String, Object> details =
                b.get("artifact") instanceof Map
                    ? (Map<String, Object>) b.get("artifact")
                    : Map.of();
            UUID file = details.get("file_id") == null ? null : Kernel.uuid(details.get("file_id"));
            if (file != null)
              k.row(
                  "SELECT id FROM files WHERE id=? AND owner_id=? AND status='READY' FOR SHARE",
                  file,
                  owner);
            if (details.get("poster_file_id") != null)
              k.row(
                  "SELECT id FROM files WHERE id=? AND owner_id=? AND status='READY' FOR SHARE",
                  Kernel.uuid(details.get("poster_file_id")),
                  owner);
            String source =
                k.encode(
                    Map.of(
                        "content",
                        content,
                        "source_run_id",
                        b.get("run_id"),
                        "format",
                        "markdown",
                        "media",
                        details));
            k.db.update(
                "INSERT INTO artifact_versions(id,artifact_id,revision,source,file_id,sha256,source_job_id) VALUES(?,?,1,?::jsonb,?,?,?)",
                Kernel.id(),
                artifact,
                source,
                file,
                Kernel.hash(source),
                Kernel.uuid(b.get("run_id")));
          }
          UUID resultMessage = chat.append(conv, "assistant", content, dedupe);
          if (Set.of("RESEARCH", "TRAVEL", "GAME", "DIAGRAM", "IMAGE", "AUDIO", "VIDEO")
              .contains(kind)) {
            var data = new LinkedHashMap<String, Object>();
            data.put("kind", kind);
            data.put("run_id", b.get("run_id"));
            data.put("title", "任务作品已保存");
            if (Set.of("IMAGE", "AUDIO", "VIDEO").contains(kind)
                && b.get("artifact") instanceof Map<?, ?> audio) {
              data.put("file_id", audio.get("file_id"));
              data.put("mock", audio.get("mock"));
              data.put("model_id", audio.get("model_id"));
              data.put("duration_ms", audio.get("duration_ms"));
              data.put("poster_file_id", audio.get("poster_file_id"));
            }
            var card =
                Map.of(
                    "schema_version",
                    1,
                    "card_id",
                    Kernel.id(),
                    "conversation_id",
                    conv,
                    "message_id",
                    resultMessage,
                    "type",
                    kind.equals("AUDIO")
                        ? "generated_audio_player"
                        : kind.equals("VIDEO")
                            ? "generated_video_player"
                            : kind.equals("IMAGE") ? "image_gallery" : "artifact_preview",
                    "data",
                    data,
                    "actions",
                    List.of("open_workspace"));
            k.db.update(
                "UPDATE messages SET cards=?::jsonb WHERE id=?",
                k.encode(List.of(card)),
                resultMessage);
            chat.event(conv, "message.cards", Map.of("message_id", resultMessage));
          }
          if ("COMPUTER".equals(kind)
              && b.get("artifact") instanceof Map<?, ?> transferred
              && transferred.get("file") instanceof Map<?, ?> fileData) {
            UUID fileId = Kernel.uuid(fileData.get("id"));
            var ownedFile =
                k.row(
                    "SELECT id,name,size_bytes,mime_type FROM files WHERE id=? AND owner_id=? AND status='READY'",
                    fileId,
                    owner);
            var fileCard =
                Map.of(
                    "schema_version",
                    1,
                    "card_id",
                    Kernel.id(),
                    "conversation_id",
                    conv,
                    "message_id",
                    resultMessage,
                    "type",
                    "file_attachment",
                    "actions",
                    List.of("download"),
                    "data",
                    ownedFile);
            k.db.update(
                "UPDATE messages SET cards=?::jsonb WHERE id=?",
                k.encode(List.of(fileCard)),
                resultMessage);
            chat.event(conv, "message.cards", Map.of("message_id", resultMessage));
          }
          if ("COMPUTER".equals(kind)
              && b.get("artifact") instanceof Map<?, ?> computer
              && computer.get("action_id") != null) {
            var card =
                Map.of(
                    "schema_version",
                    1,
                    "card_id",
                    Kernel.id(),
                    "conversation_id",
                    conv,
                    "message_id",
                    resultMessage,
                    "type",
                    "computer_approval",
                    "actions",
                    List.of("approve"),
                    "data",
                    Map.of("action_id", computer.get("action_id")));
            k.db.update(
                "UPDATE messages SET cards=?::jsonb WHERE id=?",
                k.encode(List.of(card)),
                resultMessage);
            chat.event(conv, "message.cards", Map.of("message_id", resultMessage));
          }
          if (!Boolean.FALSE.equals(b.get("notify")))
            k.db.update(
                "INSERT INTO notifications(id,event_id,owner_id,conversation_id,run_id,action_id,title,body)"
                    + " VALUES(?,?,?,?,?,?,?,?)",
                Kernel.id(),
                event,
                owner,
                conv,
                Kernel.uuid(b.get("run_id")),
                "CONNECTOR_ACTION".equals(kind)
                        && b.get("artifact") instanceof Map<?, ?> art
                        && art.get("action") instanceof Map<?, ?> action
                    ? Kernel.uuid(action.get("action_id"))
                    : ("BROWSER".equals(kind) || "COMPUTER".equals(kind))
                            && b.get("artifact") instanceof Map<?, ?> browser
                            && browser.get("action_id") != null
                        ? Kernel.uuid(browser.get("action_id"))
                        : null,
                ("BROWSER".equals(kind) || "COMPUTER".equals(kind)) && !"result".equals(delivery)
                    ? ("COMPUTER".equals(kind) ? "Mac 操作需要你确认" : "网页任务需要你处理")
                    : NotificationTitle.label(
                        b.get("task_title"), "ERROR".equals(kind) ? "未完成" : "已完成"),
                content);
          return Map.of("ok", true);
        });
  }
}
