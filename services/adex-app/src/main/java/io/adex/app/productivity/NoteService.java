package io.adex.app.productivity;

import io.adex.kernel.Kernel;
import java.util.*;
import org.springframework.stereotype.Service;

/** Private plain-text notes, independent of agent memory and generated artifacts. */
@Service
public class NoteService {
  private final Kernel k;

  public NoteService(Kernel k) {
    this.k = k;
  }

  public Object list(UUID owner, String query) {
    if (query.length() > 200) throw Kernel.error(400, "QUERY_TOO_LONG");
    var rows =
        k.db.queryForList(
            "SELECT id,title,left(content,160) AS preview,pinned,revision,updated_at FROM notes WHERE owner_id=? AND deleted_at IS NULL AND (strpos(lower(title),lower(?))>0 OR strpos(lower(content),lower(?))>0) ORDER BY pinned DESC,updated_at DESC LIMIT 201",
            owner,
            query,
            query);
    return Map.of("items", rows.stream().limit(200).toList(), "has_more", rows.size() > 200);
  }

  public Map<String, Object> get(UUID owner, UUID id) {
    var rows =
        k.db.queryForList(
            "SELECT id,title,content,pinned,revision,updated_at FROM notes WHERE id=? AND owner_id=? AND deleted_at IS NULL",
            id,
            owner);
    if (rows.isEmpty()) throw Kernel.error(404, "NOTE_NOT_FOUND");
    return rows.getFirst();
  }

  static String content(Map<String, Object> body) {
    if (!(body.get("content") instanceof String text))
      throw Kernel.error(400, "INVALID_NOTE_CONTENT");
    if (text.length() > 100000) throw Kernel.error(413, "NOTE_TOO_LARGE");
    return text;
  }

  public Object save(UUID owner, UUID id, Map<String, Object> b) {
    String title = Kernel.text(b, "title", 200), text = content(b);
    if (!(b.get("pinned") instanceof Boolean)) throw Kernel.error(400, "INVALID_PINNED");
    if (id == null) {
      UUID created = Kernel.uuid(b.get("id"));
      // Stable client UUID makes an ambiguous create response safely retryable.
      k.db.update(
          "INSERT INTO notes(id,owner_id,title,content,pinned) VALUES(?,?,?,?,?) ON CONFLICT(id) DO NOTHING",
          created,
          owner,
          title,
          text,
          b.get("pinned"));
      return get(owner, created);
    }
    get(owner, id);
    var rows =
        k.db.queryForList(
            "UPDATE notes SET title=?,content=?,pinned=?,revision=revision+1,updated_at=now() WHERE id=? AND owner_id=? AND deleted_at IS NULL AND revision=? RETURNING id,title,content,pinned,revision,updated_at",
            title,
            text,
            b.get("pinned"),
            id,
            owner,
            Kernel.number(b, "revision"));
    if (rows.isEmpty()) throw Kernel.error(409, "REVISION_CONFLICT");
    return rows.getFirst();
  }

  public Object delete(UUID owner, UUID id, long revision) {
    get(owner, id);
    if (k.db.update(
            "UPDATE notes SET deleted_at=now(),revision=revision+1 WHERE id=? AND owner_id=? AND deleted_at IS NULL AND revision=?",
            id,
            owner,
            revision)
        != 1) throw Kernel.error(409, "REVISION_CONFLICT");
    return Map.of("ok", true);
  }
}
