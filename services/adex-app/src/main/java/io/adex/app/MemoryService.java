package io.adex.app;

import io.adex.kernel.Kernel;
import java.util.*;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class MemoryService {
  final Kernel k;

  public MemoryService(Kernel k) {
    this.k = k;
  }

  public Map<String, Object> save(UUID owner, Map<String, Object> b) {
    String content = Kernel.text(b, "content", 2000), hash = Kernel.memoryHash(content);
    return k.tx.execute(
        s -> {
          k.row("SELECT id FROM users WHERE id=? FOR UPDATE", owner);
          if (k.db.queryForObject(
                  "SELECT count(*) FROM memory_tombstones WHERE owner_id=? AND content_hash=?",
                  Integer.class,
                  owner,
                  hash)
              > 0) throw Kernel.error(409, "MEMORY_TOMBSTONED");
          var refs = new ArrayList<Object>();
          if (b.containsKey("source_message_id")) {
            UUID ref = Kernel.uuid(b.get("source_message_id"));
            k.row(
                "SELECT m.id FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE"
                    + " m.id=? AND c.owner_id=? AND c.deleted_at IS NULL",
                ref,
                owner);
            refs.add(ref);
          }
          int inserted =
              k.db.update(
                  "INSERT INTO memories(id,owner_id,content,content_hash,source_refs)"
                      + " VALUES(?,?,?,?,?::jsonb) ON CONFLICT(owner_id,content_hash) DO NOTHING",
                  Kernel.id(),
                  owner,
                  content,
                  hash,
                  k.encode(refs));
          if (inserted == 1) {
            k.db.update("UPDATE users SET memory_revision=memory_revision+1 WHERE id=?", owner);
            var mem =
                k.row("SELECT id FROM memories WHERE owner_id=? AND content_hash=?", owner, hash);
            index(mem.get("id"), 1);
          }
          return k.row(
              "SELECT * FROM memories WHERE owner_id=? AND content_hash=? AND deleted_at IS NULL",
              owner,
              hash);
        });
  }

  public void remove(UUID owner, UUID id) {
    k.tx.executeWithoutResult(
        s -> {
          k.row("SELECT id FROM users WHERE id=? FOR UPDATE", owner);
          var m = k.row("SELECT * FROM memories WHERE id=? AND owner_id=? FOR UPDATE", id, owner);
          k.db.update(
              "INSERT INTO memory_tombstones(owner_id,content_hash) VALUES(?,?) ON CONFLICT DO"
                  + " NOTHING",
              owner,
              m.get("content_hash"));
          k.db.update(
              "UPDATE memories SET deleted_at=COALESCE(deleted_at,now()),revision=revision+1 WHERE"
                  + " id=?",
              id);
          k.db.update(
              "UPDATE users SET"
                  + " memory_revision=memory_revision+1,forgotten_before=clock_timestamp() WHERE"
                  + " id=?",
              owner);
          k.db.update("DELETE FROM summaries WHERE owner_id=?", owner);
          index(id, ((Number) m.get("revision")).longValue() + 1);
        });
  }

  void index(Object id, long revision) {
    k.db.update(
        "INSERT INTO outbox(id,kind,resource_id) VALUES(?,?,?) ON CONFLICT DO NOTHING",
        Kernel.id(),
        "memory.index:" + revision,
        id);
  }

  public Map<String, Object> correct(UUID owner, UUID id, Map<String, Object> b) {
    return k.tx.execute(
        s -> {
          remove(owner, id);
          return save(owner, b);
        });
  }

  @Scheduled(fixedDelay = 3000)
  public void extract() {
    try {
      for (var job :
          k.db.queryForList(
              "SELECT * FROM outbox WHERE kind='memory.extract' AND delivered_at IS NULL AND"
                  + " next_attempt_at<=now() ORDER BY next_attempt_at LIMIT 10")) {
        try {
          k.tx.executeWithoutResult(
              s -> {
                var t =
                    k.row(
                        "SELECT t.*,m.content,m.seq,m.created_at AS message_created FROM turns t"
                            + " JOIN messages m ON m.id=t.id WHERE t.id=?",
                        job.get("resource_id"));
                UUID owner = (UUID) t.get("owner_id"), conv = (UUID) t.get("conversation_id");
                var u = k.row("SELECT * FROM users WHERE id=? FOR UPDATE", owner);
                var conversation = k.row("SELECT deleted_at FROM conversations WHERE id=? AND owner_id=? FOR UPDATE", conv, owner);
                if (conversation.get("deleted_at") != null) {
                  k.db.update("UPDATE outbox SET delivered_at=now() WHERE id=?", job.get("id"));
                  return;
                }
                // Ignore extraction from any pre-forgetting message, even if its outbox was
                // delayed.
                if (u.get("forgotten_before") == null
                    || ((java.sql.Timestamp) t.get("message_created"))
                        .after((java.sql.Timestamp) u.get("forgotten_before"))) {
                  String content = String.valueOf(t.get("content"));
                  String fact =
                      content.startsWith("记住：")
                          ? content.substring(3)
                          : content.startsWith("记住:") ? content.substring(3) : null;
                  if (!Boolean.FALSE.equals(k.decode(String.valueOf(u.get("settings"))).get("memory_enabled")) && fact != null && !fact.isBlank() && fact.length() <= 2000) {
                    try {
                      save(
                          owner,
                          Map.of("content", fact, "source_message_id", t.get("id").toString()));
                    } catch (Kernel.Problem e) {
                      if (!e.code.equals("MEMORY_TOMBSTONED")) throw e;
                    }
                  }
                  var all =
                      k.db.queryForList(
                          "SELECT id,seq,role,content FROM messages WHERE conversation_id=? AND"
                              + " seq<=? AND (?::timestamptz IS NULL OR created_at>?::timestamptz)"
                              + " ORDER BY seq LIMIT 200",
                          conv,
                          ((Number) t.get("seq")).longValue() - 24,
                          u.get("forgotten_before"),
                          u.get("forgotten_before"));
                  if (!all.isEmpty()) {
                    StringBuilder summary = new StringBuilder();
                    var refs = new ArrayList<Object>();
                    for (var m : all) {
                      summary
                          .append(m.get("role"))
                          .append(": ")
                          .append(
                              String.valueOf(m.get("content"))
                                  .substring(
                                      0, Math.min(160, String.valueOf(m.get("content")).length())))
                          .append("\n");
                      refs.add(m.get("id"));
                      if (summary.length() > 6000) break;
                    }
                    long rev =
                        k.db.queryForObject(
                            "SELECT memory_revision FROM users WHERE id=?", Long.class, owner);
                    k.db.update(
                        "INSERT INTO"
                            + " summaries(conversation_id,owner_id,covered_to_seq,memory_revision,content,source_refs,summarizer_version)"
                            + " VALUES(?,?,?,?,?,?::jsonb,'extractive-v1') ON"
                            + " CONFLICT(conversation_id) DO UPDATE SET"
                            + " covered_to_seq=excluded.covered_to_seq,memory_revision=excluded.memory_revision,content=excluded.content,source_refs=excluded.source_refs,updated_at=now()",
                        conv,
                        owner,
                        all.get(Math.max(0, refs.size() - 1)).get("seq"),
                        rev,
                        summary.toString(),
                        k.encode(refs));
                  }
                }
                k.db.update("UPDATE outbox SET delivered_at=now() WHERE id=?", job.get("id"));
              });
        } catch (Exception e) {
          k.db.update(
              "UPDATE outbox SET attempt_count=attempt_count+1,next_attempt_at=now()+interval '30"
                  + " seconds' WHERE id=?",
              job.get("id"));
        }
      }
    } catch (Exception ignored) {
      /* PostgreSQL unavailable: no in-memory mutation. */
    }
  }
}
