package io.adex.app.productivity;

import io.adex.app.conversation.ConversationStore;
import io.adex.kernel.Kernel;
import java.util.*;
import org.springframework.stereotype.Service;

/** Authoritative source -> model draft -> PG save; never hold a lock across the model call. */
@Service
public class NoteConversionService {
  private final Kernel k;
  private final ConversationStore conversations;
  private final NoteService notes;

  public NoteConversionService(Kernel k, ConversationStore conversations, NoteService notes) {
    this.k = k;
    this.conversations = conversations;
    this.notes = notes;
  }

  public Object convert(UUID owner, Map<String, Object> body) {
    UUID conv = Kernel.uuid(body.get("conversation_id")),
        message = Kernel.uuid(body.get("message_id"));
    conversations.own(owner, conv);
    var source =
        k.db.queryForList(
            "SELECT content FROM messages WHERE id=? AND conversation_id=? AND role='assistant'",
            message,
            conv);
    if (source.isEmpty()) throw Kernel.error(404, "ASSISTANT_MESSAGE_NOT_FOUND");
    var existing =
        k.db.queryForList(
            "SELECT id FROM notes WHERE owner_id=? AND source_message_id=?", owner, message);
    if (!existing.isEmpty()) return notes.get(owner, (UUID) existing.getFirst().get("id"));
    var generated =
        (Map<String, Object>)
            k.call(
                "agent",
                "note:compose",
                owner,
                conv,
                "POST",
                "/internal/agent/note-compose",
                Map.of(
                    "owner_id",
                    owner,
                    "conversation_id",
                    conv,
                    "message_id",
                    message,
                    "content",
                    source.getFirst().get("content")));
    String title = Kernel.text(generated, "title", 200), content = NoteService.content(generated);
    if (content.isBlank()) throw Kernel.error(502, "NOTE_COMPOSITION_FAILED");
    return k.tx.execute(
        tx -> {
          // Recheck deletion after generation; serializes against conversation deletion.
          k.row(
              "SELECT id FROM conversations WHERE id=? AND owner_id=? AND deleted_at IS NULL FOR SHARE",
              conv,
              owner);
          k.db.update(
              "INSERT INTO notes(id,owner_id,title,content,source_message_id) VALUES(?,?,?,?,?) ON CONFLICT(owner_id,source_message_id) WHERE source_message_id IS NOT NULL DO NOTHING",
              Kernel.id(),
              owner,
              title,
              content,
              message);
          UUID id =
              k.db.queryForObject(
                  "SELECT id FROM notes WHERE owner_id=? AND source_message_id=?",
                  UUID.class,
                  owner,
                  message);
          return notes.get(owner, id);
        });
  }
}
