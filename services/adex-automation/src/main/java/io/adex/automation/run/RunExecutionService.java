package io.adex.automation.run;

import io.adex.kernel.Kernel;
import java.time.*;
import java.util.*;
import org.springframework.stereotype.Service;

/** Owns RunExecution transaction boundaries. Claims are verified by the HTTP adapter. */
@Service
public class RunExecutionService {
  private final Kernel k;

  public RunExecutionService(Kernel k) {
    this.k = k;
  }

  public Object claim(Map<String, Object> claims, Map<String, Object> b) {

    String worker = Kernel.text(b, "worker_id", 128);
    return k.tx.execute(
        s -> {
          var expired =
              k.db.queryForList(
                  "SELECT * FROM runs WHERE status='RUNNING' AND lease_until<clock_timestamp()"
                      + " ORDER BY lease_until FOR UPDATE SKIP LOCKED LIMIT 20");
          for (var lost : expired) {
            k.db.update(
                "UPDATE attempts SET status='LOST',ended_at=now() WHERE id=? AND status='RUNNING'",
                lost.get("attempt_id"));
            k.db.update(
                "UPDATE runs SET status=CASE WHEN attempts>=max_attempts THEN 'FAILED' ELSE"
                    + " 'QUEUED' END,lease_until=NULL,error_code='LEASE_EXPIRED',updated_at=now()"
                    + " WHERE id=?",
                lost.get("id"));
          }
          var eligible =
              k.db.queryForList(
                  "SELECT * FROM runs WHERE status='QUEUED' AND attempts<max_attempts ORDER BY"
                      + " created_at FOR UPDATE SKIP LOCKED LIMIT 1");
          if (eligible.isEmpty()) return Map.of("run", Map.of());
          var run = eligible.getFirst();
          UUID attempt = Kernel.id();
          var updated =
              k.row(
                  "UPDATE runs SET"
                      + " status='RUNNING',epoch=epoch+1,attempts=attempts+1,attempt_id=?,worker_id=?,lease_until=clock_timestamp()+interval"
                      + " '60 seconds',updated_at=now() WHERE id=? RETURNING *",
                  attempt,
                  worker,
                  run.get("id"));
          k.db.update(
              "INSERT INTO attempts(id,run_id,epoch,worker_id) VALUES(?,?,?,?)",
              attempt,
              run.get("id"),
              updated.get("epoch"),
              worker);
          return Map.of("run", updated);
        });
  }

  public Object authorizeEffect(Map<String, Object> claims, UUID id, Map<String, Object> b) {
    var c = claims;
    var run = k.row("SELECT * FROM runs WHERE id=?", id);
    if (!run.get("owner_id").toString().equals(c.get("owner")))
      throw Kernel.error(403, "SCOPE_DENIED");
    boolean live =
        k.db.queryForObject(
            "SELECT status='RUNNING' AND epoch=? AND attempt_id=? AND lease_until>clock_timestamp() FROM runs WHERE id=?",
            Boolean.class,
            Kernel.number(b, "epoch"),
            Kernel.uuid(b.get("attempt_id")),
            id);
    if (Set.of("CALENDAR", "CONNECTOR_ACTION").contains(run.get("kind"))) {
      live =
          live
              && k.db.queryForObject(
                  "SELECT request->>'approval_id'=? FROM runs WHERE id=?",
                  Boolean.class,
                  String.valueOf(b.get("approval_id")),
                  id);
    } else if (run.get("kind").equals("BROWSER")) {
      live = live && id.toString().equals(String.valueOf(b.get("browser_run_id")));
    } else if (run.get("kind").equals("COMPUTER")) {
      live = live && id.toString().equals(String.valueOf(b.get("computer_run_id")));
    } else if (run.get("kind").equals("CONNECTOR_SYNC")) {
      live =
          live
              && k.db.queryForObject(
                  "SELECT request->>'connection_id'=? FROM runs WHERE id=?",
                  Boolean.class,
                  String.valueOf(b.get("connection_id")),
                  id);
    } else
      live =
          live
              && Set.of("IMAGE", "AUDIO", "VIDEO").contains(run.get("kind"))
              && id.toString().equals(String.valueOf(b.get("request_key")));
    if (!live) throw Kernel.error(409, "STALE_EXECUTION");
    String computerFile = "";
    if ("COMPUTER".equals(run.get("kind"))
        && k.decode(String.valueOf(run.get("request"))).get("params") instanceof Map<?, ?> params
        && params.get("file_path") instanceof String path) computerFile = path;
    return Map.of(
        "ok",
        true,
        "origin_conversation_id",
        run.get("origin_conversation_id"),
        "kind",
        run.get("kind"),
        "computer_file_path",
        computerFile);
  }

  public Object heartbeat(Map<String, Object> claims, UUID id, Map<String, Object> b) {
    return k.tx.execute(
        s -> {
          authorize(claims, id, b);
          k.db.update(
              "UPDATE runs SET lease_until=clock_timestamp()+interval '60 seconds',updated_at=now()"
                  + " WHERE id=?",
              id);
          return Map.of("ok", true);
        });
  }

  /**
   * Validate the immutable Agent object before the short authoritative Automation transaction. A
   * failed reference commit leaves an auditable orphan, never an invented recovery point.
   */
  public Object checkpoint(Map<String, Object> claims, UUID id, Map<String, Object> b) {
    var cp = verifyCheckpoint(claims, id, b);
    String logical = Kernel.text(cp, "logical_key", 80);
    return k.tx.execute(
        s -> {
          var run = authorize(claims, id, b);
          var existing =
              k.db.queryForList(
                  "SELECT checkpoint_ref FROM steps WHERE run_id=? AND logical_key=?", id, logical);
          if (!existing.isEmpty()) {
            if (!existing
                .getFirst()
                .get("checkpoint_ref")
                .toString()
                .equals(b.get("checkpoint_ref"))) throw Kernel.error(409, "CHECKPOINT_CONFLICT");
            return Map.of("ok", true);
          }
          k.db.update(
              "INSERT INTO steps(run_id,logical_key,checkpoint_ref,epoch,attempt_id)"
                  + " VALUES(?,?,?,?,?)",
              id,
              logical,
              Kernel.uuid(b.get("checkpoint_ref")),
              b.get("epoch"),
              Kernel.uuid(b.get("attempt_id")));
          k.db.update(
              "UPDATE runs SET checkpoint_ref=?,memory_revision=?,updated_at=now() WHERE id=?",
              Kernel.uuid(b.get("checkpoint_ref")),
              Kernel.number(cp, "memory_revision"),
              id);
          return Map.of("ok", true);
        });
  }

  /** Commit the waiting checkpoint before releasing the worker lease. */
  public Object suspend(Map<String, Object> claims, UUID id, Map<String, Object> b) {
    var cp = verifyCheckpoint(claims, id, b);
    Map<String, Object> state = (Map<String, Object>) cp.get("state");
    if (!Set.of("browser_waiting", "computer_waiting").contains(state.get("phase")))
      throw Kernel.error(409, "WAITING_CHECKPOINT_REQUIRED");
    return k.tx.execute(
        tx -> {
          var run = authorize(claims, id, b);
          if (!Set.of("BROWSER", "COMPUTER").contains(run.get("kind"))
              || !String.valueOf(run.get("checkpoint_ref")).equals(b.get("checkpoint_ref")))
            throw Kernel.error(409, "UNCOMMITTED_CHECKPOINT");
          k.db.update(
              "UPDATE runs SET status='WAITING_INPUT',epoch=epoch+1,lease_until=NULL,updated_at=now() WHERE id=?",
              id);
          k.db.update(
              "UPDATE attempts SET status='WAITING_INPUT',ended_at=now() WHERE id=?",
              run.get("attempt_id"));
          UUID event = Kernel.id();
          String delivery = "waiting:" + run.get("epoch");
          var payload = new LinkedHashMap<String, Object>();
          payload.put("event_id", event);
          payload.put("run_id", id);
          payload.put("owner_id", run.get("owner_id"));
          payload.put("origin_conversation_id", run.get("origin_conversation_id"));
          payload.put("memory_revision", cp.get("memory_revision"));
          payload.put("kind", run.get("kind"));
          payload.put("delivery_key", delivery);
          payload.put("schema_version", 1);
          payload.put("content", Kernel.text(state, "content", 64000));
          payload.put("artifact", state.getOrDefault("artifact", Map.of()));
          k.db.update(
              "INSERT INTO outbox(id,run_id,payload,delivery_key) VALUES(?,?,?::jsonb,?) ON CONFLICT(run_id,delivery_key) DO NOTHING",
              event,
              id,
              k.encode(payload),
              delivery);
          return Map.of("ok", true, "status", "WAITING_INPUT");
        });
  }

  public Object complete(Map<String, Object> claims, UUID id, Map<String, Object> b) {
    var cp = verifyCheckpoint(claims, id, b);
    Map<String, Object> state = (Map<String, Object>) cp.get("state");
    if (!"result".equals(state.get("phase"))) throw Kernel.error(409, "RESULT_CHECKPOINT_REQUIRED");
    String content = Kernel.text(state, "content", 64000);
    return k.tx.execute(
        s -> {
          // Serialize surfacing for concurrent occurrences before taking a Run lock.
          // This short transaction contains no LLM/network work. Delete may lock
          // schedule -> Run, so never add a schedule row lock after this Run lock.
          var schedule =
              k.db.queryForList(
                  "SELECT schedule_id FROM runs WHERE id=? AND owner_id=?",
                  id,
                  Kernel.uuid(claims.get("owner")));
          if (!schedule.isEmpty() && schedule.getFirst().get("schedule_id") != null)
            k.db.queryForList(
                "SELECT pg_advisory_xact_lock(hashtextextended(?,0))",
                "notification:" + schedule.getFirst().get("schedule_id"));
          var run = authorize(claims, id, b);
          if (!b.get("checkpoint_ref").equals(String.valueOf(run.get("checkpoint_ref"))))
            throw Kernel.error(409, "UNCOMMITTED_CHECKPOINT");
          String observationFingerprint =
              io.adex.automation.schedule.NotificationRules.observationFingerprint(state);
          k.db.update(
              "UPDATE runs SET status='COMPLETED',result=?,observation_fingerprint=?,lease_until=NULL,updated_at=clock_timestamp() WHERE id=?",
              content,
              observationFingerprint,
              id);
          k.db.update(
              "UPDATE attempts SET status='COMPLETED',ended_at=now() WHERE id=?",
              run.get("attempt_id"));
          // A check may finish without interrupting the user. Keep its durable result,
          // checkpoint and outbox; suppress only identical consecutive check notifications.
          boolean notify = true;
          var request = k.decode(String.valueOf(run.get("request")));
          if (io.adex.automation.schedule.NotificationRules.conditional(request))
            notify = io.adex.automation.schedule.NotificationRules.conditionMet(request, state);
          else if (run.get("schedule_id") != null
              && "CHANGES_ONLY".equals(request.get("notification_policy"))) {
            var previous =
                k.db.queryForList(
                    "SELECT result,observation_fingerprint FROM runs WHERE schedule_id=? AND id<>? AND status='COMPLETED' ORDER BY updated_at DESC LIMIT 1",
                    run.get("schedule_id"),
                    id);
            notify =
                previous.isEmpty()
                    || io.adex.automation.schedule.NotificationRules.observationChanged(
                        observationFingerprint, content, previous.getFirst());
          }
          // Read without taking a schedule lock after the Run lock (delete locks in reverse order).
          // A tightened rule must silence old snapshots lacking its matching assessment.
          if (run.get("schedule_id") != null) {
            var schedules =
                k.db.queryForList(
                    "SELECT task_request FROM schedules WHERE id=?", run.get("schedule_id"));
            if (!schedules.isEmpty()) {
              var current = k.decode(String.valueOf(schedules.getFirst().get("task_request")));
              if (io.adex.automation.schedule.NotificationRules.conditional(current))
                notify =
                    notify
                        && io.adex.automation.schedule.NotificationRules.conditionMet(
                            current, state);
            }
          }
          UUID event = Kernel.id();
          var payload =
              new LinkedHashMap<String, Object>(
                  Map.of(
                      "event_id",
                      event,
                      "run_id",
                      id,
                      "owner_id",
                      run.get("owner_id"),
                      "origin_conversation_id",
                      run.get("origin_conversation_id"),
                      "content",
                      content,
                      "memory_revision",
                      cp.get("memory_revision"),
                      "schema_version",
                      1,
                      "kind",
                      run.get("kind"),
                      "artifact",
                      state.getOrDefault("artifact", Map.of())));
          payload.put("notify", notify);
          Object taskTitle = run.get("instruction");
          if (run.get("schedule_id") != null) {
            var titles =
                k.db.queryForList(
                    "SELECT title FROM schedules WHERE id=? AND owner_id=?",
                    run.get("schedule_id"),
                    run.get("owner_id"));
            if (!titles.isEmpty()) taskTitle = titles.getFirst().get("title");
          }
          payload.put("task_title", taskTitle);
          k.db.update(
              "INSERT INTO outbox(id,run_id,payload) VALUES(?,?,?::jsonb) ON CONFLICT(run_id,delivery_key) DO"
                  + " NOTHING",
              event,
              id,
              k.encode(payload));
          return Map.of("ok", true);
        });
  }

  public Object fail(Map<String, Object> claims, UUID id, Map<String, Object> b) {
    String code = Kernel.text(b, "code", 80);
    if (!code.matches("[A-Z_0-9]+")) throw Kernel.error(400, "INVALID_ERROR_CODE");
    return k.tx.execute(
        s -> {
          var run = authorize(claims, id, b);
          String status = code.equals("PROVIDER_UNKNOWN") ? "UNKNOWN" : "FAILED";
          k.db.update(
              "UPDATE runs SET status=?,error_code=?,lease_until=NULL,updated_at=now() WHERE id=?",
              status,
              code,
              id);
          k.db.update(
              "UPDATE attempts SET status=?,ended_at=now() WHERE id=?",
              status,
              run.get("attempt_id"));
          if (b.get("memory_revision") instanceof Number) {
            UUID event = Kernel.id();
            String message =
                code.equals("MUSIC_DAILY_LIMIT")
                    ? "今天的生成额度已用完，请明天重试或调整账户的生成额度。"
                    : code.equals("MEDIA_PROVIDER_ACCESS_DENIED")
                        ? ("AUDIO".equals(run.get("kind"))
                            ? "音乐生成未完成：百炼拒绝访问当前音频模型。请检查模型权限、API Key 和余额；本次没有生成音频。"
                            : "生成未完成：百炼拒绝访问该模型，请检查对应模型权限。")
                        : code.startsWith("MUSIC_")
                            ? "音乐生成未完成：供应商接口拒绝请求或未配置音乐权限。请检查音乐 API 的权限、模型和余额后再发起新请求。"
                            : "本次任务未完成（" + code + "），请查看运行记录。";
            if (code.startsWith("BROWSER_ERR_") || code.equals("BROWSER_NAVIGATION_TIMEOUT"))
              message = "网页连接暂时未能建立，尚未取得查询结果，也未提交操作。请稍后重试；如需登录或验证，会在当前会话展示。";
            if (code.startsWith("COMPUTER_"))
              message =
                  switch (code) {
                    case "COMPUTER_FILE_NOT_REQUESTED" -> "本次请求没有指定需要回传的文件。请告诉我准确文件名，再把它作为附件发送。";
                    case "COMPUTER_FILE_ROOT_NOT_GRANTED", "COMPUTER_FILE_OUTSIDE_GRANTED_ROOT" ->
                        "该文件不在本机已配置的文档访问目录中，暂时无法发送。";
                    case "COMPUTER_FILE_ACCESS_DENIED" -> "macOS 暂未允许读取该文件，请检查它的访问权限。";
                    case "COMPUTER_FILE_UNAVAILABLE", "COMPUTER_REGULAR_FILE_REQUIRED" ->
                        "没有找到可读取的普通文件。请确认文件名；当前不支持发送整个文件夹或应用程序目录。";
                    case "COMPUTER_FILE_SIZE_LIMIT" -> "该附件超过当前 25 MB 的回传上限，请选择较小文件。";
                    case "COMPUTER_SEARCH_PAGE_UNAVAILABLE",
                        "COMPUTER_SEARCH_NO_VERIFIED_RESULTS" ->
                        "Chrome 已打开，但这次未读取到可核实的搜索结果，请稍后重试。";
                    case "COMPUTER_APP_NOT_INSTALLED" -> "没有找到指定的本机应用，请确认安装情况或提供准确名称。";
                    case "COMPUTER_CONTROL_NOT_ALLOWED", "COMPUTER_APP_CONTROLS_UNAVAILABLE" ->
                        "当前应用的这个控件暂时无法操作，这一步尚未完成。";
                    default -> "本机操作这一步未完成，请查看运行记录中的具体原因。";
                  };
            if (code.equals("PROVIDER_UNKNOWN")) message = "本次供应商调用结果未知，系统已停止自动重试，请核对运行记录。";
            var payload =
                new LinkedHashMap<String, Object>(
                    Map.of(
                        "event_id",
                        event,
                        "run_id",
                        id,
                        "owner_id",
                        run.get("owner_id"),
                        "origin_conversation_id",
                        run.get("origin_conversation_id"),
                        "content",
                        message,
                        "memory_revision",
                        b.get("memory_revision"),
                        "schema_version",
                        1,
                        "kind",
                        "ERROR"));
            payload.put("task_title", run.get("instruction"));
            boolean conditionalFailure =
                io.adex.automation.schedule.NotificationRules.conditional(
                    k.decode(String.valueOf(run.get("request"))));
            if (run.get("schedule_id") != null) {
              var schedules =
                  k.db.queryForList(
                      "SELECT task_request FROM schedules WHERE id=?", run.get("schedule_id"));
              if (!schedules.isEmpty())
                conditionalFailure |=
                    io.adex.automation.schedule.NotificationRules.conditional(
                        k.decode(String.valueOf(schedules.getFirst().get("task_request"))));
            }
            if (conditionalFailure) payload.put("notify", false);
            k.db.update(
                "INSERT INTO outbox(id,run_id,payload) VALUES(?,?,?::jsonb) ON CONFLICT(run_id,delivery_key) DO NOTHING",
                event,
                id,
                k.encode(payload));
          }
          return Map.of("ok", true);
        });
  }

  public Object checkpointRefs(Map<String, Object> claims, UUID id) {
    var c = claims;
    k.row("SELECT id FROM runs WHERE id=? AND owner_id=?", id, Kernel.uuid(c.get("owner")));
    var refs =
        k.db.queryForList("SELECT checkpoint_ref FROM steps WHERE run_id=?", id).stream()
            .map(row -> row.get("checkpoint_ref").toString())
            .toList();
    return Map.of("refs", refs);
  }

  Map<String, Object> authorize(Map<String, Object> claims, UUID id, Map<String, Object> b) {
    var c = claims;
    var run = k.row("SELECT * FROM runs WHERE id=? FOR UPDATE", id);
    if (!run.get("owner_id").toString().equals(c.get("owner")))
      throw Kernel.error(403, "SCOPE_DENIED");
    boolean live =
        k.db.queryForObject(
            "SELECT status='RUNNING' AND epoch=? AND attempt_id=? AND lease_until>clock_timestamp()"
                + " FROM runs WHERE id=?",
            Boolean.class,
            Kernel.number(b, "epoch"),
            Kernel.uuid(b.get("attempt_id")),
            id);
    if (!live) throw Kernel.error(409, "STALE_EXECUTION");
    return run;
  }

  Map<String, Object> verifyCheckpoint(Map<String, Object> claims, UUID id, Map<String, Object> b) {
    var c = claims;
    UUID ref = Kernel.uuid(b.get("checkpoint_ref"));
    var cp =
        k.call(
            "agent",
            "checkpoint:read",
            c.get("owner"),
            ref,
            "GET",
            "/internal/checkpoints/" + ref,
            null);
    if (!id.toString().equals(cp.get("run_id"))
        || Kernel.number(b, "epoch") != Kernel.number(cp, "epoch")
        || !String.valueOf(b.get("attempt_id")).equals(cp.get("attempt_id"))
        || !c.get("owner").equals(cp.get("owner_id")))
      throw Kernel.error(409, "INVALID_CHECKPOINT");
    return cp;
  }
}
