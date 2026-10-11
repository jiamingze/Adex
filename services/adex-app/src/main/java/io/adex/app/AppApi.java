package io.adex.app;

import io.adex.kernel.Kernel;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.util.*;
import java.util.concurrent.*;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@RestController
public class AppApi {
  final Kernel k;
  final Auth auth;
  final ChatStore chat;
  final MemoryService memory;

  public AppApi(Kernel k, Auth a, ChatStore c, MemoryService m) {
    this.k = k;
    auth = a;
    chat = c;
    memory = m;
  }

  @PostMapping("/api/v1/auth/login")
  public Object login(@RequestBody Map<String, Object> b, HttpServletRequest r,HttpServletResponse response) {
    auth.checkOrigin(r);
    String username = Kernel.text(b, "username", 128), password = Kernel.text(b, "password", 256);
    String bucket = Kernel.hash(r.getRemoteAddr() + ":" + username);
    int count =
        k.db.queryForObject(
            "INSERT INTO login_limits(bucket,window_start,attempts)"
                + " VALUES(?,date_trunc('minute',now()),1) ON CONFLICT(bucket) DO UPDATE SET"
                + " attempts=CASE WHEN login_limits.window_start=date_trunc('minute',now()) THEN"
                + " login_limits.attempts+1 ELSE 1 END,window_start=date_trunc('minute',now())"
                + " RETURNING attempts",
            Integer.class,
            bucket);
    if (count > 10) throw Kernel.error(429, "LOGIN_RATE_LIMITED");
    var rows = k.db.queryForList("SELECT * FROM users WHERE username=?", username);
    String hash =
        rows.isEmpty()
            ? "$2a$12$F9AMygRTzNMkdZ72NMFN8eTHskPt.pGS6WRLfVZyC23xYeFLMFx8a"
            : String.valueOf(rows.getFirst().get("password_hash"));
    if (!auth.passwords.matches(password, hash) || rows.isEmpty())
      throw Kernel.error(401, "INVALID_CREDENTIALS");
    if(Boolean.TRUE.equals(rows.getFirst().get("is_guest")))throw Kernel.error(401,"INVALID_CREDENTIALS");
    return auth.issue((UUID)rows.getFirst().get("id"),username,false,response);
  }

  @PostMapping("/api/v1/auth/guest")
  public Object guest(HttpServletRequest r,HttpServletResponse response){
    auth.checkOrigin(r);
    var existing=auth.sessionOwner(r);
    if(existing.isPresent()){
      var user=k.row("SELECT username,is_guest FROM users WHERE id=?",existing.get());
      return Map.of("token",auth.sessionToken(r),"username",user.get("username"),"is_guest",user.get("is_guest"));
    }
    auth.rate(r,"guest",10);UUID id=Kernel.id();String username="guest_"+id;
    k.db.update("INSERT INTO users(id,username,password_hash,is_guest,settings) VALUES(?,?, '!',true,'{\"memory_enabled\":false}'::jsonb)",id,username);
    return auth.issue(id,username,true,response);
  }
  @PostMapping("/api/v1/auth/register")
  public Object register(@RequestBody Map<String,Object>b,HttpServletRequest r,HttpServletResponse response){
    auth.checkOrigin(r);auth.rate(r,"register",10);
    String username=Kernel.text(b,"username",32).toLowerCase(Locale.ROOT),password=Kernel.text(b,"password",128);
    if(!username.matches("[a-z0-9][a-z0-9_-]{2,31}")||username.startsWith("guest_"))throw Kernel.error(400,"INVALID_USERNAME");

    UUID id=auth.sessionOwner(r).orElseGet(Kernel::id);String hash=auth.passwords.encode(password);
    try{k.tx.executeWithoutResult(tx->{
      var rows=k.db.queryForList("SELECT is_guest FROM users WHERE id=? FOR UPDATE",id);
      if(!rows.isEmpty()){
        if(!Boolean.TRUE.equals(rows.getFirst().get("is_guest")))throw Kernel.error(409,"ALREADY_REGISTERED");
        k.db.update("UPDATE users SET username=?,password_hash=?,is_guest=false,settings=settings||'{\"memory_enabled\":true}'::jsonb WHERE id=?",username,hash,id);
        k.db.update("DELETE FROM sessions WHERE owner_id=?",id);
      }else k.db.update("INSERT INTO users(id,username,password_hash) VALUES(?,?,?)",id,username,hash);
    });}catch(org.springframework.dao.DuplicateKeyException e){throw Kernel.error(409,"USERNAME_TAKEN");}
    return auth.issue(id,username,false,response);
  }

  @PostMapping("/api/v1/auth/logout")
  public Object logout(HttpServletRequest r,HttpServletResponse response) {
    response.addHeader("Set-Cookie","adex_session=; Path=/api/; HttpOnly; SameSite=Lax; Max-Age=0");
    k.db.update(
        "DELETE FROM sessions WHERE token_hash=?",
        Kernel.hash(auth.sessionToken(r)));
    return Map.of("ok", true);
  }

  @GetMapping("/api/v1/me")
  public Object me(HttpServletRequest r) {
    return k.row("SELECT id,username,is_guest,memory_revision FROM users WHERE id=?", auth.owner(r));
  }

  @GetMapping("/api/v1/capabilities")
  public Object capabilities() {
    return Map.of(
        "chat_provider",
        Kernel.env("ADEX_MODEL_PROVIDER", "minimax"),
        "chat_model",
        Kernel.env("ADEX_MODEL_PROVIDER", "minimax").equals("qwen") ? Kernel.env("DASHSCOPE_CHAT_MODEL", "qwen3.8-max") : Kernel.env("MINIMAX_MODEL", "MiniMax-M2.5"),
        "music_provider", Kernel.env("ADEX_MUSIC_PROVIDER", "mock"),
        "music_model", Kernel.env("DASHSCOPE_MUSIC_MODEL", ""),
        "music_max_seconds", 600,
        "video_provider", Kernel.env("ADEX_VIDEO_PROVIDER", "mock"),
        "search_provider",
        "tavily",
        "offline_notifications",
        Kernel.env("ADEX_SMTP_HOST","").isBlank()?"BLOCKED_EXTERNAL":"SMTP",
        "other_features",
        "FEATURE_NOT_ENABLED");
  }

  @GetMapping("/api/v1/conversations")
  public Object conversations(
      HttpServletRequest r, @RequestParam(defaultValue = "2100-01-01T00:00:00Z") String before) {
    return Kernel.items(
        k.db.queryForList(
            "SELECT id,CASE WHEN title='新对话' THEN coalesce((SELECT left(regexp_replace(m.content,'\\s+',' ','g'),24) FROM messages m WHERE m.conversation_id=conversations.id AND m.role='user' ORDER BY m.seq LIMIT 1),title) ELSE title END AS title,created_at FROM conversations WHERE owner_id=? AND deleted_at IS NULL AND"
                + " created_at<?::timestamptz ORDER BY created_at DESC,id DESC LIMIT 100",
            auth.owner(r),
            before));
  }

  @PostMapping("/api/v1/conversations")
  public Object create(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    UUID id = Kernel.id();
    k.db.update(
        "INSERT INTO conversations(id,owner_id,title) VALUES(?,?,?)",
        id,
        auth.owner(r),
        Kernel.text(b, "title", 200));
    return k.row("SELECT id,title,created_at FROM conversations WHERE id=?", id);
  }

  @GetMapping("/api/v1/conversations/{id}/messages")
  public Object messages(
      HttpServletRequest r,
      @PathVariable UUID id,
      @RequestParam(defaultValue = "0") long after_seq,
      @RequestParam(defaultValue = "100") int limit) {
    return k.tx.execute(
        tx -> {
          chat.own(auth.owner(r), id);
          k.row("SELECT id FROM conversations WHERE id=? FOR SHARE", id);
          var result = new LinkedHashMap<String, Object>();
          result.put(
              "items",
              k.db.queryForList(
                  "SELECT id,seq,role,content,cards,created_at FROM messages WHERE conversation_id=? AND"
                      + " seq>? ORDER BY seq LIMIT ?",
                  id,
                  after_seq,
                  Math.min(200, Math.max(1, limit))));
          result.put(
              "turns",
              k.db.queryForList(
                  "SELECT id,status,error_code FROM turns WHERE conversation_id=? ORDER BY"
                      + " created_at DESC LIMIT 5",
                  id));
          result.put("event_seq", chat.own(auth.owner(r), id).get("next_event_seq"));
          result.put("partial", k.db.queryForObject("SELECT coalesce(string_agg(e.payload->>'text','' ORDER BY e.seq),'') FROM events e JOIN turns t ON t.id::text=e.payload->>'turn_id' WHERE e.conversation_id=? AND e.type='token.delta' AND t.status='RUNNING'",String.class,id));
          result.put("progress", k.db.queryForObject("SELECT coalesce((SELECT e.payload->>'text' FROM events e JOIN turns t ON t.id::text=e.payload->>'turn_id' WHERE e.conversation_id=? AND e.type='turn.progress' AND t.status='RUNNING' ORDER BY e.seq DESC LIMIT 1),'')",String.class,id));
          return result;
        });
  }

  @PostMapping("/api/v1/conversations/{id}/messages")
  public Object send(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> b) {
    return chat.send(auth.owner(r), id, b);
  }

  @GetMapping(
      value = "/api/v1/conversations/{id}/events",
      produces = MediaType.TEXT_EVENT_STREAM_VALUE)
  public SseEmitter events(
      HttpServletRequest r,
      @PathVariable UUID id,
      @RequestParam(defaultValue = "0") long after_seq,
      @RequestHeader(value = "Last-Event-ID", required = false) Long last) {
    chat.own(auth.owner(r), id);
    long start = last == null ? after_seq : last;
    SseEmitter emitter = new SseEmitter(45000L);
    String sessionHash = Kernel.hash(auth.sessionToken(r));
    Thread.startVirtualThread(
        () -> {
          long seq = start, deadline = System.currentTimeMillis() + 44000;
          try {
            while (System.currentTimeMillis() < deadline) {
              if (k.db.queryForObject(
                      "SELECT count(*) FROM sessions WHERE token_hash=? AND expires_at>now()",
                      Integer.class,
                      sessionHash)
                  == 0) break;
              for (var e :
                  k.db.queryForList(
                      "SELECT * FROM events WHERE conversation_id=? AND seq>? ORDER BY seq LIMIT"
                          + " 100",
                      id,
                      seq)) {
                seq = ((Number) e.get("seq")).longValue();
                emitter.send(
                    SseEmitter.event()
                        .id(String.valueOf(seq))
                        .name(String.valueOf(e.get("type")))
                        .data(k.decode(String.valueOf(e.get("payload")))));
              }
              emitter.send(SseEmitter.event().comment("keepalive"));
              Thread.sleep(500);
            }
            emitter.complete();
          } catch (Exception e) {
            emitter.complete();
          }
        });
    return emitter;
  }

  @GetMapping("/api/v1/memories")
  public Object memories(HttpServletRequest r) {
    return Kernel.items(
        k.db.queryForList(
            "SELECT id,content,source_refs,revision,created_at FROM memories WHERE owner_id=? AND"
                + " deleted_at IS NULL ORDER BY created_at DESC LIMIT 200",
            auth.owner(r)));
  }

  @PostMapping("/api/v1/memories")
  public Object memory(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    return memory.save(auth.owner(r), b);
  }

  @DeleteMapping("/api/v1/memories/{id}")
  public Object forget(HttpServletRequest r, @PathVariable UUID id) {
    memory.remove(auth.owner(r), id);
    return Map.of("ok", true);
  }

  @PatchMapping("/api/v1/memories/{id}")
  public Object correct(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> b) {
    return memory.correct(auth.owner(r), id, b);
  }

  @GetMapping("/api/v1/automations")
  public Object schedules(HttpServletRequest r) {
    return k.call(
        "automation", "schedule:read", auth.owner(r), null, "GET", "/internal/automations", null);
  }

  @PostMapping("/api/v1/automations")
  public Object schedule(
      HttpServletRequest r,
      @RequestBody Map<String, Object> b,
      @RequestHeader("Idempotency-Key") String key) {
    UUID owner = auth.owner(r), conv = Kernel.uuid(b.get("origin_conversation_id"));
    chat.own(owner, conv);
    if (key.isBlank() || key.length() > 128) throw Kernel.error(400, "INVALID_IDEMPOTENCY_KEY");
    var body = new LinkedHashMap<>(b);
    body.put("idempotency_key", key);
    return k.call(
        "automation", "schedule:write", owner, null, "POST", "/internal/automations", body);
  }

  @PatchMapping("/api/v1/automations/{id}")
  public Object update(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> b) {
    return k.call(
        "automation",
        "schedule:write",
        auth.owner(r),
        id,
        "PATCH",
        "/internal/automations/" + id,
        b);
  }

  @PostMapping("/api/v1/tasks")
  public Object createTask(HttpServletRequest r,@RequestBody Map<String,Object> body,@RequestHeader("Idempotency-Key") String key){
    UUID owner=auth.owner(r);chat.own(owner,Kernel.uuid(body.get("origin_conversation_id")));
    var b=new HashMap<>(body);b.put("idempotency_key",key);
    return k.call("automation","task:write",owner,null,"POST","/internal/tasks",b);
  }

  @GetMapping("/api/v1/tasks")
  public Object tasks(HttpServletRequest r) {
    return k.call("automation", "run:read", auth.owner(r), null, "GET", "/internal/runs", null);
  }

  @PostMapping("/api/v1/tasks/{id}/cancel")
  public Object cancel(HttpServletRequest r, @PathVariable UUID id) {
    return k.call(
        "automation",
        "run:cancel",
        auth.owner(r),
        id,
        "POST",
        "/internal/runs/" + id + "/cancel",
        Map.of());
  }

  @GetMapping("/api/v1/notifications")
  public Object notifications(HttpServletRequest r) {
    return Kernel.items(
        k.db.queryForList(
            "SELECT * FROM notifications WHERE owner_id=? ORDER BY created_at DESC LIMIT 100",
            auth.owner(r)));
  }

  @PostMapping("/api/v1/notifications/{id}/read")
  public Object read(HttpServletRequest r, @PathVariable UUID id) {
    if (k.db.update(
            "UPDATE notifications SET read=true WHERE id=? AND owner_id=?", id, auth.owner(r))
        != 1) throw Kernel.error(404, "NOT_FOUND");
    return Map.of("ok", true);
  }

  @GetMapping("/internal/context/{id}")
  public Object context(
      HttpServletRequest r,
      @PathVariable UUID id,
      @RequestParam(defaultValue = "9223372036854775807") long up_to_seq) {
    var claims = k.require(r, "agent", "context:read", id);
    return chat.context(Kernel.uuid(claims.get("owner")), id, up_to_seq);
  }

  @GetMapping("/api/v1/monitors") public Object monitors(HttpServletRequest r){return k.call("automation","monitor:read",auth.owner(r),null,"GET","/internal/monitors",null);}
  @PostMapping("/api/v1/monitors") public Object monitor(HttpServletRequest r,@RequestBody Map<String,Object> b){chat.own(auth.owner(r),Kernel.uuid(b.get("origin_conversation_id")));return k.call("automation","monitor:write",auth.owner(r),null,"POST","/internal/monitors",b);}
  @DeleteMapping("/api/v1/monitors/{id}") public Object cancelMonitor(HttpServletRequest r,@PathVariable UUID id){return k.call("automation","monitor:write",auth.owner(r),id,"DELETE","/internal/monitors/"+id,null);}
  @PostMapping("/internal/monitors/attach") public Object monitorAttach(HttpServletRequest r,@RequestBody Map<String,Object> b){
    UUID owner=Kernel.uuid(b.get("owner_id")),conv=Kernel.uuid(b.get("origin_conversation_id")),event=Kernel.uuid(b.get("event_id"));
    var claims=k.require(r,"automation","monitor:attach",conv);if(!owner.toString().equals(claims.get("owner")))throw Kernel.error(403,"SCOPE_DENIED");String content=Kernel.text(b,"content",64000);
    return k.tx.execute(s->{k.row("SELECT id FROM users WHERE id=? FOR SHARE",owner);var conversation=k.row("SELECT id,deleted_at FROM conversations WHERE id=? AND owner_id=? FOR UPDATE",conv,owner);
      if(k.db.update("INSERT INTO consumed_events(event_id) VALUES(?) ON CONFLICT DO NOTHING",event)==0)return Map.of("ok",true);
      if(conversation.get("deleted_at")!=null)return Map.of("ok",true,"discarded","CONVERSATION_DELETED");
      chat.append(conv,"assistant",content,"monitor:"+event);k.db.update("INSERT INTO notifications(id,event_id,owner_id,conversation_id,title,body) VALUES(?,?,?,?,?,?)",Kernel.id(),event,owner,conv,"监控发现新信息",content);return Map.of("ok",true);});
  }

  @PostMapping("/internal/results/attach")
  public Object attach(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    UUID owner = Kernel.uuid(b.get("owner_id")),
        conv = Kernel.uuid(b.get("origin_conversation_id")),
        event = Kernel.uuid(b.get("event_id"));
    var claims = k.require(r, "automation", "result:attach", conv);
    if (!owner.toString().equals(claims.get("owner"))) throw Kernel.error(403, "SCOPE_DENIED");
    String content = Kernel.text(b, "content", 64000);
    return k.tx.execute(
        s -> {
          var u = k.row("SELECT memory_revision FROM users WHERE id=? FOR SHARE", owner);
          var conversation=k.row("SELECT id,deleted_at FROM conversations WHERE id=? AND owner_id=? FOR UPDATE", conv,owner);
          if (k.db.update(
                  "INSERT INTO consumed_events(event_id) VALUES(?) ON CONFLICT DO NOTHING", event)
              == 0) return Map.of("ok", true, "deduplicated", true);
          if(conversation.get("deleted_at")!=null)return Map.of("ok",true,"discarded","CONVERSATION_DELETED");
          if (((Number) u.get("memory_revision")).longValue()
              != Kernel.number(b, "memory_revision"))
            return Map.of("ok", true, "discarded", "MEMORY_REVISION_CHANGED");
          if(!k.db.queryForList("SELECT id FROM messages WHERE conversation_id=? AND dedupe_key=?",conv,"run:"+b.get("run_id")).isEmpty())
            return Map.of("ok",true,"deduplicated",true);
          String kind=String.valueOf(b.getOrDefault("kind","CHAT"));
          if(Set.of("RESEARCH","TRAVEL","GAME","DIAGRAM","IMAGE","AUDIO","VIDEO").contains(kind)){
            UUID artifact=Kernel.id();String artifactKind=kind.equals("RESEARCH")?"REPORT":kind;
            k.db.update("INSERT INTO artifacts(id,owner_id,kind,title,revision,origin_conversation_id,source_run_id) VALUES(?,?,?,?,1,?,?)",artifact,owner,artifactKind,"任务作品 · "+kind,conv,Kernel.uuid(b.get("run_id")));
            Map<String,Object> details=b.get("artifact") instanceof Map ? (Map<String,Object>) b.get("artifact") : Map.of();
            UUID file=details.get("file_id")==null?null:Kernel.uuid(details.get("file_id"));
            if(file!=null)k.row("SELECT id FROM files WHERE id=? AND owner_id=? AND status='READY' FOR SHARE",file,owner);
            if(details.get("poster_file_id")!=null)k.row("SELECT id FROM files WHERE id=? AND owner_id=? AND status='READY' FOR SHARE",Kernel.uuid(details.get("poster_file_id")),owner);
            String source=k.encode(Map.of("content",content,"source_run_id",b.get("run_id"),"format","markdown","media",details));
            k.db.update("INSERT INTO artifact_versions(id,artifact_id,revision,source,file_id,sha256,source_job_id) VALUES(?,?,1,?::jsonb,?,?,?)",Kernel.id(),artifact,source,file,Kernel.hash(source),Kernel.uuid(b.get("run_id")));
          }
          UUID resultMessage=chat.append(conv, "assistant", content, "run:" + b.get("run_id"));
          if(Set.of("RESEARCH","TRAVEL","GAME","DIAGRAM","IMAGE","AUDIO","VIDEO").contains(kind)){
            var data=new LinkedHashMap<String,Object>();data.put("kind",kind);data.put("run_id",b.get("run_id"));data.put("title","任务作品已保存");if(Set.of("AUDIO","VIDEO").contains(kind)&&b.get("artifact") instanceof Map<?,?> audio){data.put("file_id",audio.get("file_id"));data.put("mock",audio.get("mock"));data.put("model_id",audio.get("model_id"));data.put("duration_ms",audio.get("duration_ms"));data.put("poster_file_id",audio.get("poster_file_id"));}
            var card=Map.of("schema_version",1,"card_id",Kernel.id(),"conversation_id",conv,"message_id",resultMessage,"type",kind.equals("AUDIO")?"generated_audio_player":kind.equals("VIDEO")?"generated_video_player":"artifact_preview","data",data,"actions",List.of("open_workspace"));
            k.db.update("UPDATE messages SET cards=?::jsonb WHERE id=?",k.encode(List.of(card)),resultMessage);chat.event(conv,"message.cards",Map.of("message_id",resultMessage));
          }
          k.db.update(
              "INSERT INTO notifications(id,event_id,owner_id,conversation_id,title,body)"
                  + " VALUES(?,?,?,?,?,?)",
              Kernel.id(),
              event,
              owner,
              conv,
              "任务已完成",
              content);
          return Map.of("ok", true);
        });
  }

  @PostMapping("/api/v1/automations/draft")
  public Object draft(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    UUID owner = auth.owner(r),
        id = Kernel.uuid(b.get("request_id")),
        conv = Kernel.uuid(b.get("origin_conversation_id"));
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
