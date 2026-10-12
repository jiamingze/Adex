package io.adex.app.connector;

import io.adex.app.conversation.ConversationStore;
import io.adex.kernel.Kernel;
import java.util.*;
import org.springframework.stereotype.Service;

/** Public application boundary. Tools exclusively owns external credentials and effects. */
@Service
public class ConnectorGateway {
  private final Kernel k;
  private final ConversationStore chat;

  public ConnectorGateway(Kernel k, ConversationStore chat) {
    this.k = k;
    this.chat = chat;
  }

  public Object list(UUID owner) {
    return k.call("tools", "connector:read", owner, null, "GET", "/internal/connectors", null);
  }

  public Object authorize(UUID owner, String session, Map<String, Object> body) {
    var data = new HashMap<>(body);
    data.put("session_binding", session);
    return k.call(
        "tools",
        "connector:write",
        owner,
        null,
        "POST",
        "/internal/connectors/google/authorize",
        data);
  }

  public Object callback(UUID owner, String session, String state, String code) {
    if (state.length() > 180 || code.length() > 4096)
      throw Kernel.error(400, "INVALID_OAUTH_CALLBACK");
    return k.call(
        "tools",
        "connector:write",
        owner,
        null,
        "POST",
        "/internal/connectors/google/callback",
        Map.of("session_binding", session, "state", state, "code", code));
  }

  public Object connection(UUID owner, UUID id, String action, Map<String, Object> body) {
    if (!Set.of("query", "revoke").contains(action))
      throw Kernel.error(400, "INVALID_CONNECTOR_ACTION");
    return k.call(
        "tools",
        action.equals("query") ? "connector:read" : "connector:write",
        owner,
        id,
        "POST",
        "/internal/connectors/" + id + "/" + action,
        body);
  }

  public Object sync(UUID owner, UUID id, Map<String, Object> body) {
    UUID conv = Kernel.uuid(body.get("origin_conversation_id"));
    chat.own(owner, conv);
    // Validate connection ownership before creating any durable Run.
    var connections =
        k.call("tools", "connector:read", owner, null, "GET", "/internal/connectors", null);
    boolean found =
        ((List<Map<String, Object>>) connections.get("items"))
            .stream()
                .anyMatch(
                    x ->
                        id.toString().equals(String.valueOf(x.get("id")))
                            && "ACTIVE".equals(x.get("status")));
    if (!found) throw Kernel.error(404, "CONNECTOR_NOT_FOUND");
    return k.call(
        "automation",
        "task:write",
        owner,
        null,
        "POST",
        "/internal/tasks",
        Map.of(
            "kind",
            "CONNECTOR_SYNC",
            "instruction",
            "检查已授权服务的变化与重要事项",
            "origin_conversation_id",
            conv,
            "connection_id",
            id,
            "query",
            body.getOrDefault("query", Map.of()),
            "idempotency_key",
            Kernel.text(body, "idempotency_key", 128)));
  }

  public Object watch(UUID owner, UUID id, Map<String, Object> b) {
    UUID conv = Kernel.uuid(b.get("origin_conversation_id"));
    chat.own(owner, conv);
    var connections =
        k.call("tools", "connector:read", owner, null, "GET", "/internal/connectors", null);
    var schedules =
        k.call("automation", "schedule:read", owner, null, "GET", "/internal/automations", null);
    for (var schedule : ((List<Map<String, Object>>) schedules.get("items"))) {
      if ("CONNECTOR_SYNC".equals(schedule.get("task_kind"))
          && Set.of("ACTIVE", "PAUSED").contains(schedule.get("status"))
          && schedule.get("task_request") instanceof Map<?, ?> request
          && id.toString().equals(String.valueOf(request.get("connection_id"))))
        throw Kernel.error(409, "CONNECTOR_WATCH_ALREADY_EXISTS");
    }
    var connection =
        ((List<Map<String, Object>>) connections.get("items"))
            .stream()
                .filter(
                    x ->
                        id.toString().equals(String.valueOf(x.get("id")))
                            && "ACTIVE".equals(x.get("status")))
                .findFirst()
                .orElseThrow(() -> Kernel.error(404, "CONNECTOR_NOT_FOUND"));
    String service = connection.get("service").toString();
    var body = new LinkedHashMap<String, Object>();
    body.put("origin_conversation_id", conv);
    body.put("title", "检查 " + service + " 重要变化");
    body.put("instruction", "检查已授权服务的重要变化");
    body.put("kind", "INTERVAL");
    body.put("interval_seconds", 900);
    body.put("timezone", "Asia/Shanghai");
    body.put("first_fire_at", java.time.Instant.now().plusSeconds(60).toString());
    body.put("idempotency_key", Kernel.text(b, "idempotency_key", 128));
    body.put("task_kind", "CONNECTOR_SYNC");
    body.put(
        "task_request",
        Map.of(
            "connection_id",
            id,
            "query",
            service.equals("calendar") ? Map.of("window_days", 7) : Map.of("query", "in:inbox")));
    return k.call(
        "automation", "schedule:write", owner, null, "POST", "/internal/automations", body);
  }

  public Object actions(UUID owner) {
    return k.call("tools", "approval:read", owner, null, "GET", "/internal/actions", null);
  }

  public Object draft(UUID owner, Map<String, Object> body) {
    chat.own(owner, Kernel.uuid(body.get("origin_conversation_id")));
    return k.call("tools", "approval:write", owner, null, "POST", "/internal/actions", body);
  }

  public Object decide(UUID owner, UUID id, String decision, Map<String, Object> body) {
    if (!Set.of("approve", "revoke", "reconcile").contains(decision))
      throw Kernel.error(400, "INVALID_ACTION");
    var result =
        k.call(
            "tools",
            "approval:write",
            owner,
            id,
            "POST",
            "/internal/actions/" + id + "/" + decision,
            body);
    if (!decision.equals("approve") || !(result.get("request") instanceof Map<?, ?> request))
      return result;
    UUID conv = Kernel.uuid(request.get("origin_conversation_id"));
    chat.own(owner, conv);
    // Repeated clicks reuse the same logical Run; execution rechecks expiry,
    // connection rights and live epoch at Tools, not model-generated prose.
    return k.call(
        "automation",
        "task:write",
        owner,
        null,
        "POST",
        "/internal/tasks",
        Map.of(
            "kind",
            "CONNECTOR_ACTION",
            "instruction",
            "执行用户明确确认的连接服务操作",
            "approval_id",
            id,
            "origin_conversation_id",
            conv,
            "idempotency_key",
            "action:" + id));
  }
}
