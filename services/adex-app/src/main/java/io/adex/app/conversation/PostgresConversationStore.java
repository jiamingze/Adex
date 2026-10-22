package io.adex.app.conversation;

import io.adex.kernel.Kernel;
import java.util.*;
import org.springframework.stereotype.Component;

/** JDBC adapter; message sequence, dedupe and turn fencing are committed in PostgreSQL. */
@Component
public class PostgresConversationStore implements ConversationStore {
  final Kernel k;

  public PostgresConversationStore(Kernel k) {
    this.k = k;
  }

  @Override
  public Map<String, Object> own(UUID owner, UUID conv) {
    return k.row(
        "SELECT * FROM conversations WHERE id=? AND owner_id=? AND deleted_at IS NULL",
        conv,
        owner);
  }

  @Override
  public long event(UUID conv, String type, Object payload) {
    long seq =
        k.db.queryForObject(
            "UPDATE conversations SET next_event_seq=next_event_seq+1 WHERE id=? RETURNING"
                + " next_event_seq",
            Long.class,
            conv);
    k.db.update(
        "INSERT INTO events(conversation_id,seq,event_id,type,payload) VALUES(?,?,?,?,?::jsonb)",
        conv,
        seq,
        Kernel.id(),
        type,
        k.encode(payload));
    return seq;
  }

  @Override
  public UUID append(UUID conv, String role, String content, String dedupe) {
    UUID id = Kernel.id();
    long seq =
        k.db.queryForObject(
            "UPDATE conversations SET next_seq=next_seq+1 WHERE id=? RETURNING next_seq",
            Long.class,
            conv);
    k.db.update(
        "INSERT INTO messages(id,conversation_id,seq,role,content,dedupe_key) VALUES(?,?,?,?,?,?)",
        id,
        conv,
        seq,
        role,
        content,
        dedupe);
    event(
        conv,
        "message.committed",
        Map.of("message_id", id, "seq", seq, "role", role, "content", content));
    return id;
  }

  @Override
  public Map<String, Object> send(UUID owner, UUID conv, Map<String, Object> body) {
    UUID client = Kernel.uuid(body.get("client_message_id"));
    String content = Kernel.text(body, "content", 16000);
    var location = io.adex.app.location.LocationContext.normalize(body.get("client_location"));
    String locationHash = location == null ? "" : Kernel.hash(k.encode(location));
    var calendar = CalendarContext.normalize(body.get("client_calendar"));
    String calendarHash = calendar == null ? "" : Kernel.hash(k.encode(calendar));
    boolean search = Boolean.TRUE.equals(body.get("web_search"));
    String model = body.get("model") == null ? "" : String.valueOf(body.get("model"));
    if (!Set.of("", "qwen3.8-flash", "qwen3.8-max", "minimax").contains(model))
      throw Kernel.error(400, "INVALID_MODEL");
    var fileIds = new TreeSet<UUID>();
    if (body.get("file_ids") instanceof List<?> ids) {
      if (ids.size() > 5) throw Kernel.error(400, "ATTACHMENT_LIMIT");
      for (Object file : ids) fileIds.add(Kernel.uuid(file));
    }
    return k.tx.execute(
        s -> {
          var account = k.row("SELECT is_guest FROM users WHERE id=? FOR UPDATE", owner);
          own(owner, conv);
          k.row("SELECT id FROM conversations WHERE id=? FOR UPDATE", conv);
          var exists =
              k.db.queryForList(
                  "SELECT * FROM messages WHERE conversation_id=? AND client_message_id=?",
                  conv,
                  client);
          if (!exists.isEmpty()) {
            var m = exists.getFirst();
            var t = k.row("SELECT * FROM turns WHERE id=?", m.get("id"));
            if (!calendarHash.equals(t.get("calendar_hash"))
                || !locationHash.equals(t.get("location_hash"))
                || !model.equals(t.get("model"))
                || !content.equals(m.get("content"))
                || !Boolean.valueOf(search)
                    .equals(Boolean.valueOf(String.valueOf(t.get("web_search")))))
              throw Kernel.error(409, "IDEMPOTENCY_CONFLICT");
            var oldFiles =
                new TreeSet<>(
                    k.db.queryForList(
                        "SELECT file_id FROM message_files WHERE message_id=?",
                        UUID.class,
                        m.get("id")));
            if (!oldFiles.equals(fileIds)) throw Kernel.error(409, "IDEMPOTENCY_CONFLICT");
            return Map.of("message_id", m.get("id"), "status", t.get("status"));
          }
          if (Boolean.TRUE.equals(account.get("is_guest"))) {
            if (!fileIds.isEmpty()) throw Kernel.error(403, "SIGN_IN_REQUIRED");
            if (k.db.queryForObject(
                    "SELECT count(*) FROM turns WHERE owner_id=? AND created_at>=(clock_timestamp() AT TIME ZONE 'UTC')::date",
                    Integer.class,
                    owner)
                >= 8) throw Kernel.error(429, "GUEST_QUOTA_EXCEEDED");
          }
          if (k.db.queryForObject(
                  "SELECT count(*) FROM turns WHERE conversation_id=? AND status IN"
                      + " ('QUEUED','RUNNING')",
                  Integer.class,
                  conv)
              > 0) throw Kernel.error(409, "CONVERSATION_BUSY");
          UUID id = Kernel.id();
          long seq =
              k.db.queryForObject(
                  "UPDATE conversations SET next_seq=next_seq+1 WHERE id=? RETURNING next_seq",
                  Long.class,
                  conv);
          k.db.update(
              "INSERT INTO messages(id,conversation_id,seq,role,content,client_message_id)"
                  + " VALUES(?,?,?,'user',?,?)",
              id,
              conv,
              seq,
              content,
              client);
          for (UUID file : fileIds) {
            k.row(
                "SELECT id FROM files WHERE id=? AND owner_id=? AND status='READY' FOR SHARE",
                file,
                owner);
            k.db.update("INSERT INTO message_files(message_id,file_id) VALUES(?,?)", id, file);
          }
          k.db.update(
              "UPDATE conversations SET title=left(regexp_replace(?, '\\s+', ' ', 'g'),24) WHERE id=? AND (SELECT count(*) FROM messages WHERE conversation_id=? AND role='user')=1",
              content,
              conv,
              conv);
          k.db.update(
              "INSERT INTO turns(id,conversation_id,owner_id,web_search,model,client_location,location_hash,client_calendar,calendar_hash) VALUES(?,?,?,?,?,?::jsonb,?,?::jsonb,?)",
              id,
              conv,
              owner,
              search,
              model,
              location == null ? null : k.encode(location),
              locationHash,
              calendar == null ? null : k.encode(calendar),
              calendarHash);
          k.db.update(
              "INSERT INTO outbox(id,kind,resource_id) VALUES(?,'turn.dispatch',?)",
              Kernel.id(),
              id);
          event(
              conv,
              "message.committed",
              Map.of("message_id", id, "seq", seq, "role", "user", "content", content));
          return Map.of("message_id", id, "status", "QUEUED");
        });
  }

  @Override
  public Map<String, Object> context(UUID owner, UUID conv, long upto) {
    return k.tx.execute(
        s -> {
          var user =
              k.row(
                  "SELECT memory_revision,forgotten_before,settings,is_guest FROM users WHERE id=? FOR SHARE",
                  owner);
          own(owner, conv);
          var messages =
              k.db.queryForList(
                  "SELECT id,seq,role,content,created_at FROM (SELECT id,seq,role,content,created_at FROM messages WHERE"
                      + " conversation_id=? AND seq<=? AND (?::timestamptz IS NULL OR"
                      + " created_at>?::timestamptz) ORDER BY seq DESC LIMIT 24) m ORDER BY seq",
                  conv,
                  upto,
                  user.get("forgotten_before"),
                  user.get("forgotten_before"));
          var summaries =
              k.db.queryForList(
                  "SELECT content,source_refs,covered_to_seq FROM summaries WHERE conversation_id=?"
                      + " AND memory_revision=? AND covered_to_seq<?",
                  conv,
                  user.get("memory_revision"),
                  messages.isEmpty() ? 0 : messages.getFirst().get("seq"));
          var memories =
              k.db.queryForList(
                  "SELECT id,content,source_refs FROM memories WHERE owner_id=? AND deleted_at IS"
                      + " NULL AND confirmed=true ORDER BY created_at DESC LIMIT 20",
                  owner);
          // Semantic recall comes from the frozen current-turn plan. PG ownership, current
          // memory revision and tombstones remain authoritative; model IDs grant no access.
          var latestUser =
              messages.stream()
                  .filter(m -> "user".equals(m.get("role")))
                  .reduce((first, last) -> last);
          if (latestUser.isPresent()) {
            var plans =
                k.db.queryForList(
                    "SELECT input,proposal FROM memory_turn_plans WHERE turn_id=? AND owner_id=?",
                    latestUser.get().get("id"),
                    owner);
            if (!plans.isEmpty() && plans.getFirst().get("proposal") != null) {
              var plan = plans.getFirst();
              var input = k.decode(String.valueOf(plan.get("input")));
              var proposal = k.decode(String.valueOf(plan.get("proposal")));
              if (Objects.equals(
                      String.valueOf(input.get("memory_revision")),
                      String.valueOf(user.get("memory_revision")))
                  && proposal.get("recalled_ids") instanceof List<?> ids) {
                var selected = new ArrayList<Map<String, Object>>();
                for (Object candidate : ids.stream().limit(12).toList()) {
                  try {
                    var found =
                        k.db.queryForList(
                            "SELECT id,content,source_refs FROM memories WHERE id=? AND owner_id=? AND deleted_at IS NULL AND confirmed=true",
                            UUID.fromString(String.valueOf(candidate)),
                            owner);
                    selected.addAll(found);
                  } catch (IllegalArgumentException invalidId) {
                    /* Invalid model ID is not authority. */
                  }
                }
                var seen = new HashSet<Object>();
                selected.forEach(m -> seen.add(m.get("id")));
                for (var memory : memories) if (seen.add(memory.get("id"))) selected.add(memory);
                memories = selected.stream().limit(20).toList();
              }
            }
          }
          Map<String, Object> result = new LinkedHashMap<>();
          result.put("owner_id", owner);
          result.put("conversation_id", conv);
          result.put("memory_revision", user.get("memory_revision"));
          result.put("messages", messages);
          String latestRequest =
              messages.stream()
                  .filter(m -> "user".equals(m.get("role")))
                  .reduce((first, last) -> last)
                  .map(m -> String.valueOf(m.get("content")))
                  .orElse("");
          // Bounded owner-scoped read projection; goals are organization, not long-term memory.
          if (!Boolean.TRUE.equals(user.get("is_guest"))
              && (latestRequest.contains("目标")
                  || latestRequest.toLowerCase(Locale.ROOT).contains("goal")))
            result.put(
                "goals",
                k.db.queryForList(
                    "SELECT g.id,g.title,g.outcome,count(t.id) AS total,count(t.id) FILTER(WHERE t.status='DONE') AS done FROM assistant_goals g LEFT JOIN goal_tasks l ON l.goal_id=g.id LEFT JOIN matrix_tasks t ON t.id=l.task_id AND t.owner_id=g.owner_id WHERE g.owner_id=? AND g.status='ACTIVE' GROUP BY g.id ORDER BY g.created_at DESC LIMIT 10",
                    owner));
          // Personal context is a product capability, not an exact-phrase tool trigger.
          if (!Boolean.TRUE.equals(user.get("is_guest"))) {
            // Existing App-owned records only. Deleted notes are never revived from an index.
            result.put(
                "personal_context",
                Map.of(
                    "as_of",
                    messages.isEmpty()
                        ? "unknown"
                        : String.valueOf(messages.getLast().get("created_at")),
                    "read_only",
                    true,
                    "tasks",
                    k.db.queryForList(
                        "SELECT id,revision,left(title,200) AS title,important,urgent,due_at,status FROM matrix_tasks WHERE owner_id=? AND status='TODO' ORDER BY important DESC,urgent DESC,due_at ASC NULLS LAST,id LIMIT 20",
                        owner),
                    "notes",
                    k.db.queryForList(
                        "SELECT id,title,left(content,800) AS excerpt,updated_at FROM notes WHERE owner_id=? AND deleted_at IS NULL ORDER BY pinned DESC,updated_at DESC LIMIT 8",
                        owner),
                    "limits",
                    "最多20项未完成待办、8篇最近笔记摘录；不是全部资料，也不是执行回执"));
          }
          result.put(
              "memory_enabled",
              !Boolean.FALSE.equals(
                  k.decode(String.valueOf(user.get("settings"))).get("memory_enabled")));
          result.put("is_guest", user.get("is_guest"));
          var attachments = new ArrayList<Object>();
          for (var message : messages)
            attachments.addAll(
                k.db.queryForList(
                    "SELECT f.id,f.name,f.mime_type FROM message_files mf JOIN files f ON f.id=mf.file_id WHERE mf.message_id=? AND f.owner_id=? AND f.status='READY'",
                    message.get("id"),
                    owner));
          result.put("attachments", attachments);
          result.put("summary", summaries.isEmpty() ? "" : summaries.getFirst().get("content"));
          result.put(
              "memories",
              Boolean.FALSE.equals(
                      k.decode(String.valueOf(user.get("settings"))).get("memory_enabled"))
                  ? List.of()
                  : memories);
          return result;
        });
  }

  @Override
  public void finish(Map<String, Object> turn, String content, Object cards) {
    UUID owner = (UUID) turn.get("owner_id"), conv = (UUID) turn.get("conversation_id");
    k.tx.executeWithoutResult(
        s -> {
          var user = k.row("SELECT memory_revision FROM users WHERE id=? FOR SHARE", owner);
          k.row("SELECT id FROM conversations WHERE id=? FOR UPDATE", conv);
          if (!Objects.equals(
              ((Number) user.get("memory_revision")).longValue(),
              ((Number) turn.get("memory_revision")).longValue()))
            throw Kernel.error(409, "MEMORY_REVISION_CHANGED");
          int n =
              k.db.update(
                  "UPDATE turns SET status='COMPLETED',client_location=NULL,client_calendar=NULL,lease_until=NULL WHERE id=? AND epoch=? AND"
                      + " attempt_id=? AND status='RUNNING' AND lease_until>clock_timestamp()",
                  turn.get("id"),
                  turn.get("epoch"),
                  turn.get("attempt_id"));
          if (n != 1) throw Kernel.error(409, "STALE_EXECUTION");
          UUID message = append(conv, "assistant", content, "turn:" + turn.get("id"));
          var normalized = new ArrayList<Map<String, Object>>();
          if (cards instanceof List<?> values && values.size() <= 10)
            for (Object value : values) {
              if (value instanceof Map<?, ?> card) {
                var safe = new LinkedHashMap<String, Object>();
                card.forEach((key, v) -> safe.put(String.valueOf(key), v));
                safe.put(
                    "schema_version",
                    card.get("schema_version") instanceof Number ? card.get("schema_version") : 1);
                safe.put("card_id", Kernel.id());
                safe.put("conversation_id", conv);
                safe.put("message_id", message);
                normalized.add(safe);
              }
            }
          if (k.encode(normalized).length() > 64000) throw Kernel.error(413, "CARD_SIZE_LIMIT");
          k.db.update(
              "UPDATE messages SET cards=?::jsonb WHERE id=?", k.encode(normalized), message);
          k.db.update(
              "UPDATE outbox SET delivered_at=now() WHERE kind='turn.dispatch' AND resource_id=?",
              turn.get("id"));
          k.db.update(
              "INSERT INTO outbox(id,kind,resource_id) VALUES(?,'memory.extract',?) ON CONFLICT DO"
                  + " NOTHING",
              Kernel.id(),
              turn.get("id"));
          event(conv, "turn.completed", Map.of("turn_id", turn.get("id")));
        });
  }
}
