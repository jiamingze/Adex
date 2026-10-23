package io.adex.app.integration;

import io.adex.app.productivity.MatrixService;
import io.adex.kernel.Kernel;
import java.util.*;
import org.springframework.stereotype.Service;

/**
 * Model proposals cross a closed capability boundary; only committed readback becomes a receipt.
 */
@Service
public class ChatTaskActions {
  private final Kernel k;
  private final MatrixService matrix;
  private final ChatScheduleService schedules;

  public ChatTaskActions(Kernel k, MatrixService matrix, ChatScheduleService schedules) {
    this.k = k;
    this.matrix = matrix;
    this.schedules = schedules;
  }

  private void live(Map<String, Object> t) {
    k.row(
        "SELECT t.id FROM turns t JOIN conversations c ON c.id=t.conversation_id WHERE t.id=? AND t.owner_id=? AND t.epoch=? AND t.attempt_id=? AND t.status='RUNNING' AND t.lease_until>clock_timestamp() AND c.deleted_at IS NULL",
        t.get("id"),
        t.get("owner_id"),
        t.get("epoch"),
        t.get("attempt_id"));
  }

  @SuppressWarnings("unchecked")
  public Map<String, Object> execute(Map<String, Object> t, Map<String, Object> call) {
    live(t);
    UUID owner = (UUID) t.get("owner_id"),
        conv = (UUID) t.get("conversation_id"),
        turn = (UUID) t.get("id");
    if (Boolean.TRUE.equals(k.row("SELECT is_guest FROM users WHERE id=?", owner).get("is_guest")))
      throw Kernel.error(403, "SIGN_IN_REQUIRED");
    String tool = Kernel.text(call, "tool", 40);
    if (!Set.of(
            "workflow.start",
            "computer.start",
            "schedule.create",
            "schedule.update",
            "schedule.list",
            "todo.create",
            "todo.update",
            "todo.list")
        .contains(tool)) throw Kernel.error(400, "UNSUPPORTED_TASK_TOOL");
    Map<String, Object> args =
        call.get("arguments") instanceof Map<?, ?> raw ? (Map<String, Object>) raw : Map.of();
    if (tool.endsWith(".list")) return list(owner, tool);
    String hash = Kernel.hash(k.encode(new TreeMap<>(call)));
    var existing =
        k.tx.execute(
            tx -> {
              // Match conversation deletion and Turn completion. Never hold these locks across
              // HTTP.
              k.row(
                  "SELECT id FROM conversations WHERE id=? AND owner_id=? AND deleted_at IS NULL FOR UPDATE",
                  conv,
                  owner);
              k.row(
                  "SELECT id FROM turns WHERE id=? AND owner_id=? AND epoch=? AND attempt_id=? AND status='RUNNING' AND lease_until>clock_timestamp() FOR UPDATE",
                  turn,
                  owner,
                  t.get("epoch"),
                  t.get("attempt_id"));
              k.db.update(
                  "INSERT INTO chat_task_actions(turn_id,request_hash,state) VALUES(?,?,'PENDING') ON CONFLICT DO NOTHING",
                  turn,
                  hash);
              var row = k.row("SELECT * FROM chat_task_actions WHERE turn_id=?", turn);
              if (!hash.equals(row.get("request_hash")))
                throw Kernel.error(409, "IDEMPOTENCY_CONFLICT");
              return row;
            });
    if ("SUCCEEDED".equals(existing.get("state")))
      return k.decode(String.valueOf(existing.get("receipt")));
    if (tool.startsWith("todo.")) {
      return k.tx.execute(
          tx -> {
            Map<String, Object> saved;
            if (tool.equals("todo.create")) saved = matrix.fromChat(owner, conv, t, args);
            else saved = matrix.editFromChat(t, Kernel.uuid(call.get("target_id")), args);
            var receipt = new LinkedHashMap<String, Object>();
            String text = matrix.chatReceipt(saved);
            if (tool.equals("todo.update")) text = text.replace("已添加到你的待办", "已更新你的待办");
            if ("DONE".equals(saved.get("status"))) text = text.replace("**状态**：待处理", "**状态**：已完成");
            receipt.put("content", text);
            receipt.put("record_id", saved.get("id"));
            persist(t, hash, receipt);
            return receipt;
          });
    }
    Map<String, Object> receipt;
    if (tool.equals("computer.start")) {
      var capability =
          k.call("tools", "computer:read", owner, null, "GET", "/internal/computer/status", null);
      if (!"READY".equals(capability.get("availability")))
        throw Kernel.error(409, "COMPUTER_ACCESSIBILITY_PERMISSION_REQUIRED");
      String goal = Kernel.text(args, "goal", 16000), app = Kernel.text(args, "app_name", 200);
      var task =
          k.call(
              "automation",
              "task:write",
              owner,
              null,
              "POST",
              "/internal/tasks",
              Map.of(
                  "kind",
                  "COMPUTER",
                  "instruction",
                  goal,
                  "origin_conversation_id",
                  conv,
                  "idempotency_key",
                  "chat-computer:" + turn,
                  "params",
                  Map.of("app_name", app)));
      UUID computerRun = Kernel.uuid(task.get("id"));
      var savedComputer =
          k.call(
              "automation",
              "run:read",
              owner,
              computerRun,
              "GET",
              "/internal/runs/" + computerRun,
              null);
      if (!"COMPUTER".equals(savedComputer.get("kind"))
          || !goal.equals(savedComputer.get("instruction")))
        throw Kernel.error(502, "TASK_READBACK_MISMATCH");
      receipt =
          Map.of(
              "content", "已开始 Mac 应用操作：" + app + "。需要确认的动作会返回当前对话。", "record_id", task.get("id"));
    } else if (tool.equals("workflow.start")) {
      String goal = Kernel.text(args, "goal", 16000);
      if (!(args.get("acceptance") instanceof List<?> acceptance)
          || acceptance.isEmpty()
          || acceptance.size() > 12
          || acceptance.stream()
              .anyMatch(c -> !(c instanceof String text) || text.isBlank() || text.length() > 500))
        throw Kernel.error(400, "INVALID_ACCEPTANCE_CRITERIA");
      var task =
          k.call(
              "automation",
              "task:write",
              owner,
              null,
              "POST",
              "/internal/tasks",
              Map.of(
                  "kind",
                  "RESEARCH",
                  "instruction",
                  goal,
                  "origin_conversation_id",
                  conv,
                  "idempotency_key",
                  "chat-workflow:" + turn,
                  "params",
                  Map.of(
                      "agent_loop",
                      true,
                      "acceptance",
                      acceptance,
                      "original_request",
                      k.row(
                              "SELECT content FROM messages WHERE id=? AND conversation_id=?",
                              turn,
                              conv)
                          .get("content"))));
      UUID runId = Kernel.uuid(task.get("id"));
      var observed =
          k.call("automation", "run:read", owner, runId, "GET", "/internal/runs/" + runId, null);
      if (!"RESEARCH".equals(observed.get("kind")) || !goal.equals(observed.get("instruction")))
        throw Kernel.error(502, "TASK_READBACK_MISMATCH");
      receipt =
          Map.of(
              "content",
              "已开始分步研究，结果会回到当前对话。研究目标：" + goal,
              "record_id",
              runId,
              "cards",
              List.of(
                  Map.of(
                      "type",
                      "task_status",
                      "data",
                      Map.of("run_id", runId, "kind", "RESEARCH", "status", task.get("status")))));
    } else if (tool.equals("schedule.create")) receipt = schedules.create(owner, conv, turn, args);
    else {
      UUID id = Kernel.uuid(call.get("target_id"));
      var patch = new LinkedHashMap<String, Object>(args);
      patch.put("command_key", "chat-task:" + turn);
      k.call(
          "automation", "schedule:write", owner, id, "PATCH", "/internal/automations/" + id, patch);
      var current = readSchedule(owner, id);
      for (String field :
          List.of("title", "instruction", "kind", "timezone", "status", "interval_seconds"))
        if (patch.containsKey(field)
            && !String.valueOf(patch.get(field)).equals(String.valueOf(current.get(field))))
          throw Kernel.error(502, "TASK_READBACK_MISMATCH");
      if (patch.containsKey("local_time")
          && !java.time.LocalTime.parse(String.valueOf(patch.get("local_time")))
              .equals(java.time.LocalTime.parse(String.valueOf(current.get("local_time")))))
        throw Kernel.error(502, "TASK_READBACK_MISMATCH");
      if (patch.containsKey("first_fire_at")) {
        var requested = java.time.Instant.parse(String.valueOf(patch.get("first_fire_at")));
        var next = java.time.Instant.parse(String.valueOf(current.get("next_fire_at")));
        if ("DAILY".equals(current.get("kind"))
            ? next.isBefore(requested)
            : !next.equals(requested)) throw Kernel.error(502, "TASK_READBACK_MISMATCH");
      }
      var rules =
          current.get("task_request") instanceof Map<?, ?> map
              ? map
              : k.decode(String.valueOf(current.get("task_request")));
      for (String field : List.of("notification_policy", "notification_condition"))
        if (patch.containsKey(field) && !Objects.equals(patch.get(field), rules.get(field)))
          throw Kernel.error(502, "TASK_READBACK_MISMATCH");
      if (((Number) current.get("revision")).longValue()
          < ((Number) patch.get("revision")).longValue() + 1)
        throw Kernel.error(502, "TASK_READBACK_MISMATCH");
      receipt =
          Map.of(
              "content",
              "已更新自动安排：「"
                  + current.get("title")
                  + "」\n\n执行内容："
                  + current.get("instruction")
                  + "\n下次执行："
                  + current.get("next_fire_at")
                  + "（"
                  + current.get("timezone")
                  + "）\n状态："
                  + current.get("status")
                  + "\n修改已保存，影响后续执行。",
              "record_id",
              id);
    }
    live(t); // A remote command already dispatched may have committed, but a stale worker cannot
    // publish success.
    var finalReceipt = receipt;
    k.tx.executeWithoutResult(tx -> persist(t, hash, finalReceipt));
    return receipt;
  }

  private void persist(Map<String, Object> t, String hash, Map<String, Object> receipt) {
    // Lock the Turn before receipt CAS. The same fence protects visible chat completion.
    k.row(
        "SELECT id FROM turns WHERE id=? AND epoch=? AND attempt_id=? AND status='RUNNING' AND lease_until>clock_timestamp() FOR UPDATE",
        t.get("id"),
        t.get("epoch"),
        t.get("attempt_id"));
    if (k.db.update(
            "UPDATE chat_task_actions SET state='SUCCEEDED',receipt=?::jsonb WHERE turn_id=? AND request_hash=?",
            k.encode(receipt),
            t.get("id"),
            hash)
        != 1) throw Kernel.error(409, "STALE_EXECUTION");
  }

  @SuppressWarnings("unchecked")
  public Map<String, Object> readSchedule(UUID owner, UUID id) {
    var response =
        k.call("automation", "schedule:read", owner, null, "GET", "/internal/automations", null);
    return ((List<Map<String, Object>>) response.get("items"))
        .stream()
            .filter(row -> id.toString().equals(String.valueOf(row.get("id"))))
            .findFirst()
            .orElseThrow(() -> Kernel.error(502, "TASK_READBACK_MISSING"));
  }

  @SuppressWarnings("unchecked")
  private Map<String, Object> list(UUID owner, String tool) {
    List<Map<String, Object>> rows =
        tool.startsWith("schedule")
            ? (List<Map<String, Object>>)
                k.call(
                        "automation",
                        "schedule:read",
                        owner,
                        null,
                        "GET",
                        "/internal/automations",
                        null)
                    .get("items")
            : (List<Map<String, Object>>) ((Map<?, ?>) matrix.list(owner)).get("items");
    var text = new StringBuilder(tool.startsWith("schedule") ? "你的自动安排：" : "你的待办事项：");
    for (var row : rows.stream().limit(30).toList())
      text.append("\n- ")
          .append(row.get("title"))
          .append(" · ")
          .append(row.get("status"))
          .append(" · ID：")
          .append(row.get("id"));
    if (rows.isEmpty()) text.append("\n当前没有事项。");
    return Map.of("content", text.toString());
  }
}
