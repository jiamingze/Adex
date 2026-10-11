package io.adex.automation;

import io.adex.kernel.Kernel;
import jakarta.servlet.http.HttpServletRequest;
import java.sql.Timestamp;
import java.time.*;
import java.util.*;
import org.springframework.web.bind.annotation.*;

@RestController
public class AutomationApi {
  final Kernel k;

  public AutomationApi(Kernel k) {
    this.k = k;
  }

  UUID owner(HttpServletRequest r, String scope, Object resource) {
    return Kernel.uuid(k.require(r, "app", scope, resource).get("owner"));
  }

  @GetMapping("/internal/automations")
  public Object list(HttpServletRequest r) {
    return Kernel.items(
        k.db.queryForList(
            "SELECT * FROM schedules WHERE owner_id=? ORDER BY created_at DESC LIMIT 100",
            owner(r, "schedule:read", null)));
  }

  @PostMapping("/internal/automations")
  public Object create(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    UUID owner = owner(r, "schedule:write", null),
        conv = Kernel.uuid(b.get("origin_conversation_id"));
    String title = Kernel.text(b, "title", 200),
        instruction = Kernel.text(b, "instruction", 16000),
        kind = Kernel.text(b, "kind", 20),
        tz = Kernel.text(b, "timezone", 80),
        key = Kernel.text(b, "idempotency_key", 128);
    ZoneId.of(tz);
    if (!Set.of("ONCE", "INTERVAL", "DAILY").contains(kind))
      throw Kernel.error(400, "INVALID_SCHEDULE_KIND");
    Instant first = Instant.parse(Kernel.text(b, "first_fire_at", 80));
    int seconds =
        kind.equals("INTERVAL") ? Math.toIntExact(Kernel.number(b, "interval_seconds")) : 0;
    if (kind.equals("INTERVAL") && (seconds < 60 || seconds > 31536000))
      throw Kernel.error(400, "INVALID_INTERVAL");
    LocalTime time =
        kind.equals("DAILY") ? LocalTime.parse(Kernel.text(b, "local_time", 20)) : null;
    String hash = Kernel.hash(k.encode(new TreeMap<>(b)));
    return k.tx.execute(
        s -> {
          // Serialize owner+key only, independent of schedulers and other owners.
          k.db.queryForObject(
              "SELECT pg_advisory_xact_lock(hashtextextended(?,0))",
              Object.class,
              owner + ":" + key);
          var existing =
              k.db.queryForList(
                  "SELECT * FROM schedules WHERE owner_id=? AND idempotency_key=?", owner, key);
          if (!existing.isEmpty()) {
            var v = existing.getFirst();
            if (!hash.equals(v.get("request_hash")))
              throw Kernel.error(409, "IDEMPOTENCY_CONFLICT");
            return v;
          }
          Instant now =
              k.db.queryForObject("SELECT clock_timestamp()", Timestamp.class).toInstant();
          if (first.isBefore(now.minusSeconds(5))) throw Kernel.error(400, "SCHEDULE_IN_PAST");
          if (k.db.queryForObject(
                  "SELECT count(*) FROM schedules WHERE owner_id=? AND status IN"
                      + " ('ACTIVE','PAUSED')",
                  Integer.class,
                  owner)
              >= 100) throw Kernel.error(429, "SCHEDULE_LIMIT");
          Instant next =
              kind.equals("DAILY") ? ScheduleTime.nextDaily(first.minusNanos(1), tz, time) : first;
          UUID id = Kernel.id();
          k.db.update(
              "INSERT INTO"
                  + " schedules(id,owner_id,origin_conversation_id,title,instruction,kind,timezone,local_time,interval_seconds,next_fire_at,idempotency_key,request_hash)"
                  + " VALUES(?,?,?,?,?,?,?,?::time,?,?,?,?)",
              id,
              owner,
              conv,
              title,
              instruction,
              kind,
              tz,
              time == null ? null : time.toString(),
              kind.equals("INTERVAL") ? seconds : null,
              Timestamp.from(next),
              key,
              hash);
          return k.row("SELECT * FROM schedules WHERE id=?", id);
        });
  }

  @PatchMapping("/internal/automations/{id}")
  public Object update(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> b) {
    UUID owner = owner(r, "schedule:write", id);
    String status = Kernel.text(b, "status", 20);
    if (!Set.of("ACTIVE", "PAUSED", "CANCELLED").contains(status))
      throw Kernel.error(400, "INVALID_STATUS");
    long rev = Kernel.number(b, "revision");
    return k.tx.execute(
        s -> {
          var old =
              k.row("SELECT * FROM schedules WHERE id=? AND owner_id=? FOR UPDATE", id, owner);
          if (Set.of("CANCELLED", "COMPLETED").contains(String.valueOf(old.get("status"))))
            throw Kernel.error(409, "SCHEDULE_TERMINAL");
          if (((Number) old.get("revision")).longValue() != rev)
            throw Kernel.error(409, "REVISION_CONFLICT");
          k.db.update("UPDATE schedules SET status=?,revision=revision+1 WHERE id=?", status, id);
          return k.row("SELECT * FROM schedules WHERE id=?", id);
        });
  }

  @PostMapping("/internal/tasks")
  public Object task(HttpServletRequest r,@RequestBody Map<String,Object> b) {
    UUID owner=owner(r,"task:write",null), conv=Kernel.uuid(b.get("origin_conversation_id"));
    String kind=Kernel.text(b,"kind",40), instruction=Kernel.text(b,"instruction",16000), key=Kernel.text(b,"idempotency_key",128);
    if(!Set.of("RESEARCH","TRAVEL","GAME","DIAGRAM","IMAGE","AUDIO","VIDEO","CALENDAR").contains(kind))throw Kernel.error(400,"INVALID_TASK_KIND");
    String hash=Kernel.hash(k.encode(new TreeMap<>(b)));
    return k.tx.execute(tx->{
      k.db.queryForObject("SELECT pg_advisory_xact_lock(hashtextextended(?,0))",Object.class,owner+":"+key);
      var old=k.db.queryForList("SELECT * FROM runs WHERE owner_id=? AND idempotency_key=?",owner,key);
      if(!old.isEmpty()){if(!hash.equals(old.getFirst().get("request_hash")))throw Kernel.error(409,"IDEMPOTENCY_CONFLICT");return old.getFirst();}
      if(k.db.queryForObject("SELECT count(*) FROM runs WHERE owner_id=? AND status IN ('QUEUED','RUNNING')",Integer.class,owner)>=20)throw Kernel.error(429,"TASK_LIMIT");
      return k.row("INSERT INTO runs(id,owner_id,origin_conversation_id,instruction,kind,request,idempotency_key,request_hash) VALUES(?,?,?,?,?,?::jsonb,?,?) RETURNING *",Kernel.id(),owner,conv,instruction,kind,k.encode(b),key,hash);
    });
  }

  @GetMapping("/internal/runs")
  public Object runs(HttpServletRequest r) {
    return Kernel.items(
        k.db.queryForList(
            "SELECT * FROM runs WHERE owner_id=? ORDER BY created_at DESC LIMIT 100",
            owner(r, "run:read", null)));
  }

  @PostMapping("/internal/runs/{id}/cancel")
  public Object cancel(HttpServletRequest r, @PathVariable UUID id) {
    UUID owner = owner(r, "run:cancel", id);
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

  @PostMapping("/internal/runs/claim")
  public Object claim(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    k.require(r, "agent", "run:claim", null);
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

  @PostMapping("/internal/runs/{id}/authorize-effect")
  public Object authorizeEffect(HttpServletRequest r,@PathVariable UUID id,@RequestBody Map<String,Object> b){
    var c=k.require(r,"tools","effect:execute",id);
    var run=k.row("SELECT * FROM runs WHERE id=?",id);
    if(!run.get("owner_id").toString().equals(c.get("owner")))throw Kernel.error(403,"SCOPE_DENIED");
    boolean live=k.db.queryForObject("SELECT status='RUNNING' AND epoch=? AND attempt_id=? AND lease_until>clock_timestamp() FROM runs WHERE id=?",Boolean.class,Kernel.number(b,"epoch"),Kernel.uuid(b.get("attempt_id")),id);
    if(run.get("kind").equals("CALENDAR")){
      live=live&&k.db.queryForObject("SELECT request->>'approval_id'=? FROM runs WHERE id=?",Boolean.class,String.valueOf(b.get("approval_id")),id);
    }else live=live&&Set.of("IMAGE","AUDIO","VIDEO").contains(run.get("kind"))&&id.toString().equals(String.valueOf(b.get("request_key")));
    if(!live)throw Kernel.error(409,"STALE_EXECUTION");return Map.of("ok",true);
  }

  Map<String, Object> authorize(HttpServletRequest r, UUID id, Map<String, Object> b) {
    var c = k.require(r, "agent", "run:write", id);
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

  @PostMapping("/internal/runs/{id}/heartbeat")
  public Object heartbeat(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> b) {
    return k.tx.execute(
        s -> {
          authorize(r, id, b);
          k.db.update(
              "UPDATE runs SET lease_until=clock_timestamp()+interval '60 seconds',updated_at=now()"
                  + " WHERE id=?",
              id);
          return Map.of("ok", true);
        });
  }

  Map<String, Object> verifyCheckpoint(HttpServletRequest r, UUID id, Map<String, Object> b) {
    var c = k.require(r, "agent", "run:write", id);
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

  @PostMapping("/internal/runs/{id}/checkpoint")
  public Object checkpoint(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> b) {
    var cp = verifyCheckpoint(r, id, b);
    String logical = Kernel.text(cp, "logical_key", 80);
    return k.tx.execute(
        s -> {
          var run = authorize(r, id, b);
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

  @SuppressWarnings("unchecked")
  @PostMapping("/internal/runs/{id}/complete")
  public Object complete(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> b) {
    var cp = verifyCheckpoint(r, id, b);
    Map<String, Object> state = (Map<String, Object>) cp.get("state");
    if (!"result".equals(state.get("phase"))) throw Kernel.error(409, "RESULT_CHECKPOINT_REQUIRED");
    String content = Kernel.text(state, "content", 64000);
    return k.tx.execute(
        s -> {
          var run = authorize(r, id, b);
          if (!b.get("checkpoint_ref").equals(String.valueOf(run.get("checkpoint_ref"))))
            throw Kernel.error(409, "UNCOMMITTED_CHECKPOINT");
          k.db.update(
              "UPDATE runs SET status='COMPLETED',result=?,lease_until=NULL,updated_at=now() WHERE"
                  + " id=?",
              content,
              id);
          k.db.update(
              "UPDATE attempts SET status='COMPLETED',ended_at=now() WHERE id=?",
              run.get("attempt_id"));
          UUID event = Kernel.id();
          var payload =
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
                  "kind", run.get("kind"),
                  "artifact", state.getOrDefault("artifact",Map.of()));
          k.db.update(
              "INSERT INTO outbox(id,run_id,payload) VALUES(?,?,?::jsonb) ON CONFLICT(run_id) DO"
                  + " NOTHING",
              event,
              id,
              k.encode(payload));
          return Map.of("ok", true);
        });
  }

  @PostMapping("/internal/runs/{id}/fail")
  public Object fail(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> b) {
    String code = Kernel.text(b, "code", 80);
    if (!code.matches("[A-Z_0-9]+")) throw Kernel.error(400, "INVALID_ERROR_CODE");
    return k.tx.execute(
        s -> {
          var run = authorize(r, id, b);
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
          if(b.get("memory_revision") instanceof Number){
            UUID event=Kernel.id();String message=code.equals("MUSIC_DAILY_LIMIT")?"今天的生成额度已用完，请明天重试或调整账户的生成额度。":code.equals("MEDIA_PROVIDER_ACCESS_DENIED")?("AUDIO".equals(run.get("kind"))?"音乐生成未完成：百炼拒绝访问当前音频模型。请检查模型权限、API Key 和余额；本次没有生成音频。":"生成未完成：百炼拒绝访问该模型，请检查对应模型权限。"):code.startsWith("MUSIC_")?"音乐生成未完成：供应商接口拒绝请求或未配置音乐权限。请检查音乐 API 的权限、模型和余额后再发起新请求。":"本次任务未完成（"+code+"），请查看运行记录。";
            if(code.equals("PROVIDER_UNKNOWN"))message="本次供应商调用结果未知，系统已停止自动重试，请核对运行记录。";
            var payload=Map.of("event_id",event,"run_id",id,"owner_id",run.get("owner_id"),"origin_conversation_id",run.get("origin_conversation_id"),"content",message,"memory_revision",b.get("memory_revision"),"schema_version",1,"kind","ERROR");
            k.db.update("INSERT INTO outbox(id,run_id,payload) VALUES(?,?,?::jsonb) ON CONFLICT(run_id) DO NOTHING",event,id,k.encode(payload));
          }
          return Map.of("ok", true);
        });
  }

  @GetMapping("/internal/runs/{id}/checkpoint-refs")
  public Object checkpointRefs(HttpServletRequest request, @PathVariable UUID id) {
    var c = k.require(request, "agent", "run:inspect", id);
    k.row("SELECT id FROM runs WHERE id=? AND owner_id=?", id, Kernel.uuid(c.get("owner")));
    var refs =
        k.db.queryForList("SELECT checkpoint_ref FROM steps WHERE run_id=?", id).stream()
            .map(row -> row.get("checkpoint_ref").toString())
            .toList();
    return Map.of("refs", refs);
  }
}
