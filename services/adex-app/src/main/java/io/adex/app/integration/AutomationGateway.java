package io.adex.app.integration;

import io.adex.app.conversation.ConversationStore;
import io.adex.kernel.Kernel;
import java.util.*;
import org.springframework.stereotype.Service;

/** Owns AutomationGateway use cases; HTTP authentication is performed by the adapter. */
@Service
public class AutomationGateway {
  private final Kernel k;
  private final ConversationStore chat;

  public AutomationGateway(Kernel k, ConversationStore chat) {
    this.k = k;
    this.chat = chat;
  }

  public Object schedules(UUID owner) {
    return k.call("automation", "schedule:read", owner, null, "GET", "/internal/automations", null);
  }

  public Object schedule(UUID owner, Map<String, Object> b, String key) {
    if (b.containsKey("task_kind") || b.containsKey("task_request"))
      throw Kernel.error(400, "USE_CONNECTOR_WATCH_ENDPOINT");
    UUID conv = Kernel.uuid(b.get("origin_conversation_id"));
    chat.own(owner, conv);
    if (key.isBlank() || key.length() > 128) throw Kernel.error(400, "INVALID_IDEMPOTENCY_KEY");
    var body = new LinkedHashMap<>(b);
    body.put("idempotency_key", key);
    return k.call(
        "automation", "schedule:write", owner, null, "POST", "/internal/automations", body);
  }

  public Object update(UUID owner, UUID id, Map<String, Object> b) {
    return k.call(
        "automation", "schedule:write", owner, id, "PATCH", "/internal/automations/" + id, b);
  }

  public Object createTask(UUID owner, Map<String, Object> body, String key) {
    chat.own(owner, Kernel.uuid(body.get("origin_conversation_id")));
    var b = new HashMap<>(body);
    b.put("idempotency_key", key);
    return k.call("automation", "task:write", owner, null, "POST", "/internal/tasks", b);
  }

  public Object tasks(UUID owner) {
    return k.call("automation", "run:read", owner, null, "GET", "/internal/runs", null);
  }

  public Object cancel(UUID owner, UUID id) {
    return k.call(
        "automation",
        "run:cancel",
        owner,
        id,
        "POST",
        "/internal/runs/" + id + "/cancel",
        Map.of());
  }

  public Object monitors(UUID owner) {
    return k.call("automation", "monitor:read", owner, null, "GET", "/internal/monitors", null);
  }

  public Object monitor(UUID owner, Map<String, Object> b) {
    chat.own(owner, Kernel.uuid(b.get("origin_conversation_id")));
    return k.call("automation", "monitor:write", owner, null, "POST", "/internal/monitors", b);
  }

  public Object cancelMonitor(UUID owner, UUID id) {
    return k.call(
        "automation", "monitor:write", owner, id, "DELETE", "/internal/monitors/" + id, null);
  }

  public Object draft(UUID owner, Map<String, Object> b) {
    UUID id = Kernel.uuid(b.get("request_id")), conv = Kernel.uuid(b.get("origin_conversation_id"));
    chat.own(owner, conv);
    String input = Kernel.text(b, "instruction", 2000), tz = Kernel.text(b, "timezone", 80);
    java.time.ZoneId.of(tz);
    String hash =
        Kernel.hash(
            k.encode(Map.of("instruction", input, "timezone", tz, "conversation_id", conv)));
    var request =
        k.tx.execute(
            tx -> {
              k.db.queryForObject(
                  "SELECT pg_advisory_xact_lock(hashtextextended(?,0))",
                  Object.class,
                  id.toString());
              var rows = k.db.queryForList("SELECT * FROM schedule_drafts WHERE id=?", id);
              if (!rows.isEmpty()) {
                var old = rows.getFirst();
                if (!owner.equals(old.get("owner_id")) || !hash.equals(old.get("request_hash")))
                  throw Kernel.error(409, "IDEMPOTENCY_CONFLICT");
                return k.decode(String.valueOf(old.get("request")));
              }
              var payload =
                  Map.of(
                      "request_id",
                      id,
                      "owner_id",
                      owner,
                      "conversation_id",
                      conv,
                      "instruction",
                      input,
                      "timezone",
                      tz,
                      "current_time",
                      java.time.Instant.now().toString());
              k.db.update(
                  "INSERT INTO schedule_drafts(id,owner_id,conversation_id,request_hash,request)"
                      + " VALUES(?,?,?,?,?::jsonb)",
                  id,
                  owner,
                  conv,
                  hash,
                  k.encode(payload));
              return payload;
            });
    return k.call(
        "agent", "schedule:draft", owner, conv, "POST", "/internal/agent/schedule-draft", request);
  }
}
