package io.adex.automation.run;

import io.adex.kernel.Kernel;
import java.time.*;
import java.util.*;
import org.springframework.stereotype.Service;

/** Owns Run transaction boundaries. Claims are verified by the HTTP adapter. */
@Service
public class RunService {
  private final Kernel k;

  public RunService(Kernel k) {
    this.k = k;
  }

  public Object task(Map<String, Object> claims, Map<String, Object> b) {
    UUID owner = Kernel.uuid(claims.get("owner")),
        conv = Kernel.uuid(b.get("origin_conversation_id"));
    String kind = Kernel.text(b, "kind", 40),
        instruction = Kernel.text(b, "instruction", 16000),
        key = Kernel.text(b, "idempotency_key", 128);
    if (!Set.of(
            "RESEARCH",
            "TRAVEL",
            "GAME",
            "DIAGRAM",
            "IMAGE",
            "AUDIO",
            "VIDEO",
            "CALENDAR",
            "CONNECTOR_SYNC",
            "CONNECTOR_ACTION",
            "BROWSER")
        .contains(kind)) throw Kernel.error(400, "INVALID_TASK_KIND");
    String hash = Kernel.hash(k.encode(new TreeMap<>(b)));
    return k.tx.execute(
        tx -> {
          k.db.queryForObject(
              "SELECT pg_advisory_xact_lock(hashtextextended(?,0))",
              Object.class,
              owner + ":" + key);
          var old =
              k.db.queryForList(
                  "SELECT * FROM runs WHERE owner_id=? AND idempotency_key=?", owner, key);
          if (!old.isEmpty()) {
            if (!hash.equals(old.getFirst().get("request_hash")))
              throw Kernel.error(409, "IDEMPOTENCY_CONFLICT");
            return old.getFirst();
          }
          if (k.db.queryForObject(
                  "SELECT count(*) FROM runs WHERE owner_id=? AND status IN ('QUEUED','RUNNING')",
                  Integer.class,
                  owner)
              >= 20) throw Kernel.error(429, "TASK_LIMIT");
          return k.row(
              "INSERT INTO runs(id,owner_id,origin_conversation_id,instruction,kind,request,idempotency_key,request_hash) VALUES(?,?,?,?,?,?::jsonb,?,?) RETURNING *",
              Kernel.id(),
              owner,
              conv,
              instruction,
              kind,
              k.encode(b),
              key,
              hash);
        });
  }

  public Object runs(Map<String, Object> claims) {
    return Kernel.items(
        k.db.queryForList(
            "SELECT * FROM runs WHERE owner_id=? ORDER BY created_at DESC LIMIT 100",
            Kernel.uuid(claims.get("owner"))));
  }

  public Object run(Map<String, Object> claims, UUID id) {
    return k.row(
        "SELECT * FROM runs WHERE id=? AND owner_id=?", id, Kernel.uuid(claims.get("owner")));
  }

  /** User resumption requeues the same Run; attempts remain auditable. */
  public Object resume(Map<String, Object> claims, UUID id) {
    UUID owner = Kernel.uuid(claims.get("owner"));
    return k.tx.execute(
        tx -> {
          var run = k.row("SELECT * FROM runs WHERE id=? AND owner_id=? FOR UPDATE", id, owner);
          if (!"BROWSER".equals(run.get("kind"))) throw Kernel.error(409, "NOT_A_BROWSER_RUN");
          if (Set.of("QUEUED", "RUNNING").contains(run.get("status"))) return run;
          if (!"WAITING_INPUT".equals(run.get("status")))
            throw Kernel.error(409, "RUN_NOT_WAITING");
          k.db.update(
              "UPDATE runs SET status='QUEUED',epoch=epoch+1,max_attempts=max_attempts+1,error_code=NULL,updated_at=now() WHERE id=?",
              id);
          return k.row("SELECT * FROM runs WHERE id=?", id);
        });
  }

  public Object cancel(Map<String, Object> claims, UUID id) {
    UUID owner = Kernel.uuid(claims.get("owner"));
    return k.tx.execute(
        s -> {
          var run = k.row("SELECT * FROM runs WHERE id=? AND owner_id=? FOR UPDATE", id, owner);
          if (Set.of("COMPLETED", "FAILED", "CANCELLED", "UNKNOWN").contains(run.get("status")))
            return run;
          k.db.update(
              "UPDATE attempts SET status='CANCELLED',ended_at=now() WHERE id=?",
              run.get("attempt_id"));
          k.db.update(
              "UPDATE runs SET status='CANCELLED',epoch=epoch+1,lease_until=NULL,updated_at=now()"
                  + " WHERE id=?",
              id);
          return k.row("SELECT * FROM runs WHERE id=?", id);
        });
  }
}
