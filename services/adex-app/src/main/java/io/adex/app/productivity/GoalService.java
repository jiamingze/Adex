package io.adex.app.productivity;

import io.adex.kernel.Kernel;
import java.time.Instant;
import java.util.*;
import org.springframework.stereotype.Service;

/** Goals organize existing todos. Publishing a plan never creates an execution scheduler. */
@Service
public class GoalService {
  private final Kernel k;
  private final MatrixService matrix;

  public GoalService(Kernel k, MatrixService matrix) {
    this.k = k;
    this.matrix = matrix;
  }

  public Object list(UUID owner) {
    return Kernel.items(
        k
            .db
            .queryForList(
                "SELECT id FROM assistant_goals WHERE owner_id=? ORDER BY created_at DESC LIMIT 100",
                owner)
            .stream()
            .map(row -> detail(owner, (UUID) row.get("id")))
            .toList());
  }

  private Map<String, Object> detail(UUID owner, UUID id) {
    var goal =
        new LinkedHashMap<>(
            k.row("SELECT * FROM assistant_goals WHERE id=? AND owner_id=?", id, owner));
    goal.remove("request_hash");
    var tasks =
        k.db.queryForList(
            "SELECT t.* FROM goal_tasks g JOIN matrix_tasks t ON t.id=g.task_id WHERE g.goal_id=? AND t.owner_id=? ORDER BY g.position",
            id,
            owner);
    goal.put("tasks", tasks);
    goal.put("total", tasks.size());
    goal.put("done", tasks.stream().filter(t -> "DONE".equals(t.get("status"))).count());
    return goal;
  }

  public Object create(UUID owner, Map<String, Object> b) {
    UUID id = Kernel.uuid(b.get("id"));
    if (id == null) throw Kernel.error(400, "INVALID_GOAL_ID");
    String title = Kernel.text(b, "title", 200), outcome = outcome(b);
    if (!(b.get("steps") instanceof List<?> steps) || steps.size() > 12)
      throw Kernel.error(400, "INVALID_GOAL_STEPS");
    for (Object step : steps)
      if (!(step instanceof String s) || s.isBlank() || s.length() > 200)
        throw Kernel.error(400, "INVALID_GOAL_STEPS");
    String hash = Kernel.hash(k.encode(Map.of("title", title, "outcome", outcome, "steps", steps)));
    return k.tx.execute(
        tx -> {
          // Serialize only the goal UUID; retries after a lost response cannot duplicate todos.
          k.db.queryForObject(
              "SELECT pg_advisory_xact_lock(hashtextextended(?,0))", Object.class, "goal:" + id);
          var existing =
              k.db.queryForList("SELECT owner_id,request_hash FROM assistant_goals WHERE id=?", id);
          if (!existing.isEmpty()) {
            if (!owner.equals(existing.getFirst().get("owner_id")))
              throw Kernel.error(404, "NOT_FOUND");
            if (!hash.equals(existing.getFirst().get("request_hash")))
              throw Kernel.error(409, "IDEMPOTENCY_CONFLICT");
            return detail(owner, id);
          }
          if (k.db.queryForObject(
                  "SELECT count(*) FROM assistant_goals WHERE owner_id=? AND status='ACTIVE'",
                  Integer.class,
                  owner)
              >= 100) throw Kernel.error(429, "GOAL_LIMIT");
          k.db.update(
              "INSERT INTO assistant_goals(id,owner_id,title,outcome,request_hash) VALUES(?,?,?,?,?)",
              id,
              owner,
              title,
              outcome,
              hash);
          int position = 0;
          for (Object step : steps) {
            @SuppressWarnings("unchecked")
            var task =
                (Map<String, Object>)
                    matrix.save(
                        owner,
                        null,
                        Map.of(
                            "title",
                            step,
                            "description",
                            outcome,
                            "important",
                            true,
                            "urgent",
                            false,
                            "status",
                            "TODO",
                            "due_at",
                            Instant.now().plusSeconds(86400).toString()));
            k.db.update(
                "INSERT INTO goal_tasks(goal_id,task_id,position) VALUES(?,?,?)",
                id,
                task.get("id"),
                position++);
          }
          return detail(owner, id);
        });
  }

  public Object update(UUID owner, UUID id, Map<String, Object> b) {
    String title = Kernel.text(b, "title", 200),
        outcome = outcome(b),
        status = Kernel.text(b, "status", 20);
    if (!Set.of("ACTIVE", "ARCHIVED").contains(status))
      throw Kernel.error(400, "INVALID_GOAL_STATUS");
    return k.tx.execute(
        tx -> {
          k.row("SELECT id FROM assistant_goals WHERE id=? AND owner_id=? FOR UPDATE", id, owner);
          if (k.db.update(
                  "UPDATE assistant_goals SET title=?,outcome=?,status=?,revision=revision+1,updated_at=now() WHERE id=? AND owner_id=? AND revision=?",
                  title,
                  outcome,
                  status,
                  id,
                  owner,
                  Kernel.number(b, "revision"))
              != 1) throw Kernel.error(409, "REVISION_CONFLICT");
          return detail(owner, id);
        });
  }

  public Object plan(UUID owner, Map<String, Object> b) {
    UUID requestId = Kernel.uuid(b.get("request_id"));
    if (requestId == null) throw Kernel.error(400, "INVALID_GOAL_REQUEST");
    return k.call(
        "agent",
        "goal:plan",
        owner,
        null,
        "POST",
        "/internal/agent/goal-plan",
        Map.of(
            "owner_id",
            owner,
            "request_id",
            requestId,
            "title",
            Kernel.text(b, "title", 200),
            "outcome",
            outcome(b)));
  }

  private static String outcome(Map<String, Object> b) {
    if (!(b.getOrDefault("outcome", "") instanceof String s) || s.length() > 4000)
      throw Kernel.error(400, "INVALID_GOAL_OUTCOME");
    return s.strip();
  }
}
