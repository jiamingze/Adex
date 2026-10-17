package io.adex.app.conversation;

import io.adex.app.memory.MemoryService;
import io.adex.kernel.Kernel;
import java.util.*;
import org.springframework.stereotype.Service;

/** Owns Conversation use cases; HTTP authentication is performed by the adapter. */
@Service
public class ConversationService {
  private final Kernel k;
  private final ConversationStore chat;
  private final MemoryService memory;

  public ConversationService(Kernel k, ConversationStore chat, MemoryService memory) {
    this.k = k;
    this.chat = chat;
    this.memory = memory;
  }

  public Object conversations(UUID owner, String before) {
    return Kernel.items(
        k.db.queryForList(
            "SELECT id,CASE WHEN title='新对话' THEN coalesce((SELECT left(regexp_replace(m.content,'\\s+',' ','g'),24) FROM messages m WHERE m.conversation_id=conversations.id AND m.role='user' ORDER BY m.seq LIMIT 1),title) ELSE title END AS title,created_at FROM conversations WHERE owner_id=? AND deleted_at IS NULL AND"
                + " created_at<?::timestamptz ORDER BY created_at DESC,id DESC LIMIT 100",
            owner,
            before));
  }

  public Object create(UUID owner, Map<String, Object> b) {
    UUID id = Kernel.id();
    k.db.update(
        "INSERT INTO conversations(id,owner_id,title) VALUES(?,?,?)",
        id,
        owner,
        Kernel.text(b, "title", 200));
    return k.row("SELECT id,title,created_at FROM conversations WHERE id=?", id);
  }

  public Object messages(UUID owner, UUID id, long after_seq, int limit) {
    return k.tx.execute(
        tx -> {
          chat.own(owner, id);
          k.row("SELECT id FROM conversations WHERE id=? FOR SHARE", id);
          var result = new LinkedHashMap<String, Object>();
          result.put(
              "items",
              k.db.queryForList(
                  "SELECT id,seq,role,content,cards,created_at FROM messages WHERE conversation_id=? AND"
                      + " seq>? ORDER BY seq LIMIT ?",
                  id,
                  after_seq,
                  Math.min(200, Math.max(1, limit))));
          result.put(
              "turns",
              k.db.queryForList(
                  "SELECT id,status,error_code FROM turns WHERE conversation_id=? ORDER BY"
                      + " created_at DESC LIMIT 5",
                  id));
          result.put("event_seq", chat.own(owner, id).get("next_event_seq"));
          result.put(
              "partial",
              k.db.queryForObject(
                  "SELECT coalesce(string_agg(e.payload->>'text','' ORDER BY e.seq),'') FROM events e JOIN turns t ON t.id::text=e.payload->>'turn_id' WHERE e.conversation_id=? AND e.type='token.delta' AND t.status='RUNNING'",
                  String.class,
                  id));
          result.put(
              "progress",
              k.db.queryForObject(
                  "SELECT coalesce((SELECT e.payload->>'text' FROM events e JOIN turns t ON t.id::text=e.payload->>'turn_id' WHERE e.conversation_id=? AND e.type='turn.progress' AND t.status='RUNNING' ORDER BY e.seq DESC LIMIT 1),'')",
                  String.class,
                  id));
          return result;
        });
  }

  public Object send(UUID owner, UUID id, Map<String, Object> b) {
    return chat.send(owner, id, b);
  }

  public Object rename(UUID owner, UUID id, Map<String, Object> b) {
    chat.own(owner, id);
    return k.row(
        "UPDATE conversations SET title=? WHERE id=? RETURNING *",
        Kernel.text(b, "title", 200),
        id);
  }

  /**
   * Deletion takes user then conversation locks, matching memory extraction lock order.
   * Incrementing memory_revision prevents an already-running model from republishing forgotten
   * data.
   */
  public Object delete(UUID owner, UUID id) {

    return k.tx.execute(
        s -> {
          k.row("SELECT id FROM users WHERE id=? FOR UPDATE", owner);
          chat.own(owner, id);
          k.row("SELECT id FROM conversations WHERE id=? FOR UPDATE", id);
          for (var m :
              k.db.queryForList(
                  "SELECT id FROM memories WHERE owner_id=? AND deleted_at IS NULL AND EXISTS (SELECT 1 FROM messages WHERE conversation_id=? AND jsonb_exists(source_refs,messages.id::text))",
                  owner,
                  id)) memory.remove(owner, (UUID) m.get("id"));
          k.db.update("DELETE FROM summaries WHERE conversation_id=?", id);
          k.db.update("UPDATE turns SET client_location=NULL WHERE conversation_id=?", id);
          k.db.update("UPDATE users SET memory_revision=memory_revision+1 WHERE id=?", owner);
          k.db.update(
              "UPDATE turns SET status='CANCELLED',client_location=NULL,epoch=epoch+1,lease_until=NULL WHERE conversation_id=? AND status IN ('QUEUED','RUNNING')",
              id);
          k.db.update("UPDATE conversations SET deleted_at=now() WHERE id=?", id);
          return Map.of("ok", true);
        });
  }

  /**
   * Fencing advances before cancellation is published; stale workers cannot commit later deltas.
   */
  public Object stop(UUID owner, UUID id) {
    return k.tx.execute(
        s -> {
          chat.own(owner, id);
          k.row("SELECT id FROM conversations WHERE id=? FOR UPDATE", id);
          k.db.update(
              "UPDATE turns SET status='CANCELLED',client_location=NULL,epoch=epoch+1,lease_until=NULL WHERE conversation_id=? AND status IN ('QUEUED','RUNNING')",
              id);
          chat.event(id, "turn.cancelled", Map.of());
          return Map.of("ok", true);
        });
  }

  public Object search(UUID owner, String q) {
    if (q.isBlank() || q.length() > 200) throw Kernel.error(400, "INVALID_QUERY");
    return Kernel.items(
        k.db.queryForList(
            "SELECT m.id,m.conversation_id,m.content,c.title FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE c.owner_id=? AND c.deleted_at IS NULL AND (to_tsvector('simple',m.content)@@plainto_tsquery('simple',?) OR m.content ILIKE ?) ORDER BY m.created_at DESC LIMIT 50",
            owner,
            q,
            "%" + q + "%"));
  }
}
