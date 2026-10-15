package io.adex.app.conversation;

import io.adex.app.memory.MemoryChatService;
import io.adex.kernel.Kernel;
import java.io.*;
import java.net.URI;
import java.net.http.*;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class ChatWorker {
  final Kernel k;
  final ConversationStore chat;
  final MemoryChatService memoryChat;
  final Semaphore slots = new Semaphore(4);
  final ConcurrentHashMap<UUID, Map<String, Object>> active = new ConcurrentHashMap<>();

  final ConcurrentHashMap<UUID, Thread> threads = new ConcurrentHashMap<>();
  final ConcurrentHashMap<UUID, InputStream> streams = new ConcurrentHashMap<>();
  final ConcurrentHashMap<UUID, Long> deadlines = new ConcurrentHashMap<>();

  // Durable cancellation remains authoritative across replicas. Interrupt/close releases local
  // slots.
  @Scheduled(fixedDelay = 250)
  public void stopInactive() {
    for (var entry : threads.entrySet()) {
      var t = active.get(entry.getKey());
      if (t == null) continue;
      try {
        if (System.nanoTime() > deadlines.getOrDefault(entry.getKey(), Long.MAX_VALUE)) {
          k.tx.executeWithoutResult(
              tx -> {
                if (k.db.update(
                        "UPDATE turns SET status='FAILED',error_code='CHAT_TIMEOUT',lease_until=NULL WHERE id=? AND epoch=? AND attempt_id=? AND status='RUNNING'",
                        t.get("id"),
                        t.get("epoch"),
                        t.get("attempt_id"))
                    == 1)
                  chat.event(
                      (UUID) t.get("conversation_id"),
                      "turn.failed",
                      Map.of("turn_id", t.get("id"), "code", "CHAT_TIMEOUT"));
              });
        }
        int live =
            k.db.queryForObject(
                "SELECT count(*) FROM turns WHERE id=? AND epoch=? AND attempt_id=? AND status='RUNNING' AND lease_until>clock_timestamp()",
                Integer.class,
                t.get("id"),
                t.get("epoch"),
                t.get("attempt_id"));
        if (live == 0 && threads.remove(entry.getKey(), entry.getValue())) {
          entry.getValue().interrupt();
          var input = streams.remove(entry.getKey());
          if (input != null)
            Thread.startVirtualThread(
                () -> {
                  try {
                    input.close();
                  } catch (IOException ignored) {
                  }
                });
        }
      } catch (Exception ignored) {
      }
    }
  }

  public ChatWorker(Kernel k, ConversationStore chat, MemoryChatService memoryChat) {
    this.k = k;
    this.chat = chat;
    this.memoryChat = memoryChat;
  }

  @Scheduled(fixedDelay = 1000)
  public void dispatch() {
    try {
      k.db.update(
          "UPDATE turns SET status='QUEUED',lease_until=NULL WHERE status='RUNNING' AND"
              + " lease_until<clock_timestamp()");
      while (slots.tryAcquire()) {
        var t =
            k.tx.execute(
                s -> {
                  var list =
                      k.db.queryForList(
                          "SELECT * FROM turns WHERE status='QUEUED' ORDER BY created_at FOR UPDATE"
                              + " SKIP LOCKED LIMIT 1");
                  if (list.isEmpty()) return null;
                  var v = list.getFirst();
                  UUID attempt = Kernel.id();
                  return k.row(
                      "UPDATE turns SET"
                          + " status='RUNNING',epoch=epoch+1,attempt_id=?,lease_until=clock_timestamp()+interval"
                          + " '60 seconds',memory_revision=(SELECT memory_revision FROM users WHERE"
                          + " id=turns.owner_id) WHERE id=? RETURNING *",
                      attempt,
                      v.get("id"));
                });
        if (t == null) {
          slots.release();
          break;
        }
        UUID id = (UUID) t.get("id");
        active.put(id, t);
        Thread.startVirtualThread(
            () -> {
              try {
                deadlines.put(id, System.nanoTime() + Duration.ofSeconds(180).toNanos());
                threads.put(id, Thread.currentThread());
                execute(t);
              } finally {
                threads.remove(id);
                streams.remove(id);
                deadlines.remove(id);
                active.remove(id);
                slots.release();
              }
            });
      }
    } catch (Exception ignored) {
    }
  }

  @Scheduled(fixedDelay = 10000)
  public void heartbeat() {
    for (var t : active.values())
      try {
        k.db.update(
            "UPDATE turns SET lease_until=clock_timestamp()+interval '60 seconds' WHERE id=? AND"
                + " epoch=? AND attempt_id=? AND status='RUNNING' AND"
                + " lease_until>clock_timestamp()",
            t.get("id"),
            t.get("epoch"),
            t.get("attempt_id"));
      } catch (Exception ignored) {
      }
  }

  void execute(Map<String, Object> t) {
    UUID owner = (UUID) t.get("owner_id"),
        conv = (UUID) t.get("conversation_id"),
        id = (UUID) t.get("id");
    try {
      emit(t, "正在理解你的问题", "turn.progress");
      if (memoryChat.handle(t)) return;
      long upto = k.db.queryForObject("SELECT seq FROM messages WHERE id=?", Long.class, id);
      var ctx = chat.context(owner, conv, upto);
      t.put("memory_revision", ctx.get("memory_revision"));
      emit(t, "", "turn.started");
      var body =
          Map.of(
              "invocation_key",
              "chat:" + id,
              "owner_id",
              owner,
              "conversation_id",
              conv,
              "turn_id",
              id,
              "context",
              ctx,
              "web_search",
              t.get("web_search"),
              "model",
              t.get("model"));
      var req =
          HttpRequest.newBuilder(URI.create(Kernel.env("ADEX_AGENT_URL") + "/internal/agent/turns"))
              .timeout(Duration.ofSeconds(180))
              .header("Authorization", "Bearer " + k.token("agent", "turn:execute", owner, id))
              .header("Content-Type", "application/json")
              .POST(HttpRequest.BodyPublishers.ofString(k.encode(body)))
              .build();
      var res = k.http.send(req, HttpResponse.BodyHandlers.ofInputStream());
      if (res.statusCode() != 200) {
        res.body().close();
        throw Kernel.error(503, "AGENT_UNAVAILABLE");
      }
      streams.put(id, res.body());
      String finalContent = null;
      Object cards = List.of();
      StringBuilder delta = new StringBuilder();
      long last = System.currentTimeMillis();
      try (var reader =
          new BufferedReader(
              new InputStreamReader(res.body(), java.nio.charset.StandardCharsets.UTF_8))) {
        String line;
        while ((line = reader.readLine()) != null) {
          if (Thread.currentThread().isInterrupted()) throw Kernel.error(409, "STALE_EXECUTION");
          if (line.isBlank()) continue;
          var e = k.decode(line);
          String type = String.valueOf(e.get("type"));
          if (type.equals("error")) throw Kernel.error(502, String.valueOf(e.get("code")));
          if (type.equals("progress")) emit(t, String.valueOf(e.get("text")), "turn.progress");
          if (type.equals("delta")) {
            delta.append(e.get("text"));
            if (delta.length() > 64 || System.currentTimeMillis() - last > 80) {
              emit(t, delta.toString());
              delta.setLength(0);
              last = System.currentTimeMillis();
            }
          }
          if (type.equals("schedule.requested")) {
            emit(t, "正在创建定时任务", "turn.progress");
            if (Boolean.TRUE.equals(
                k.row("SELECT is_guest FROM users WHERE id=?", owner).get("is_guest"))) {
              finalContent = "Adex 支持定时任务。请先注册或登录，再发送这条请求，即可设置每天上午8点（北京时间）整理 SpaceX 最新消息。当前尚未创建任务。";
            } else {
              if (!(e.get("draft") instanceof Map<?, ?> draft))
                throw Kernel.error(400, "INVALID_SCHEDULE_KIND");
              var request = new LinkedHashMap<String, Object>();
              for (String field : List.of("title", "instruction", "kind", "timezone", "local_time"))
                request.put(field, draft.get(field));
              var zone = java.time.ZoneId.of(String.valueOf(request.get("timezone")));
              var localTime = java.time.LocalTime.parse(String.valueOf(request.get("local_time")));
              var created =
                  k.db
                      .queryForObject(
                          "SELECT created_at FROM turns WHERE id=?", java.sql.Timestamp.class, id)
                      .toInstant()
                      .atZone(zone);
              var first = created.toLocalDate().atTime(localTime).atZone(zone);
              if (!first.isAfter(created)) first = first.plusDays(1);
              request.put("first_fire_at", first.toInstant().toString());
              request.put("origin_conversation_id", conv);
              request.put("idempotency_key", "chat-schedule:" + id);
              var schedule =
                  k.call(
                      "automation",
                      "schedule:write",
                      owner,
                      null,
                      "POST",
                      "/internal/automations",
                      request);
              cards =
                  List.of(
                      Map.of(
                          "type",
                          "automation_status",
                          "data",
                          Map.of(
                              "schedule_id",
                              schedule.get("id"),
                              "local_time",
                              localTime.toString(),
                              "timezone",
                              zone.toString(),
                              "status",
                              schedule.get("status")),
                          "actions",
                          List.of("open_tasks")));
              finalContent =
                  "已设置每天 "
                      + localTime
                      + "（"
                      + zone
                      + "）执行："
                      + request.get("instruction")
                      + "。结果会回到当前对话，可在定时任务页暂停或取消。";
            }
          }
          if (type.equals("task.requested")) {
            emit(t, "正在创建任务", "turn.progress");
            if (Boolean.TRUE.equals(
                k.row("SELECT is_guest FROM users WHERE id=?", owner).get("is_guest")))
              throw Kernel.error(403, "SIGN_IN_REQUIRED");
            var request = new LinkedHashMap<String, Object>();
            request.put("kind", e.get("kind"));
            request.put("instruction", e.get("instruction"));
            request.put("origin_conversation_id", conv);
            request.put("idempotency_key", "chat-task:" + id);
            if (e.get("request") instanceof Map<?, ?> extra) {
              for (String field : List.of("provider", "rights_confirmed", "params", "browser_url"))
                if (extra.containsKey(field)) request.put(field, extra.get(field));
            }
            var task =
                k.call("automation", "task:write", owner, null, "POST", "/internal/tasks", request);
            cards =
                List.of(
                    Map.of(
                        "type",
                        "task_status",
                        "data",
                        Map.of(
                            "run_id",
                            task.get("id"),
                            "kind",
                            e.get("kind"),
                            "status",
                            task.get("status")),
                        "actions",
                        List.of("open_tasks")));
            finalContent =
                "已开始处理（"
                    + e.get("kind")
                    + "），关闭页面后会继续处理。结果将回到当前对话，并保存到作品空间。任务 ID："
                    + task.get("id");
            if ("BROWSER".equals(e.get("kind")))
              finalContent = "已开始网页操作任务。需要登录或确认提交时会暂停，请到主动助手的浏览器面板查看、接管或审批。任务 ID：" + task.get("id");
            if ("IMAGE".equals(e.get("kind"))) finalContent = "正在生成图片，完成后会直接显示在当前对话，并保存到作品空间。";
            if ("AUDIO".equals(e.get("kind")))
              finalContent = "正在创作原创音乐，完成后会在当前对话提供播放器和下载。你可以离开页面，稍后回来查看。";
          }
          if (type.equals("completed")) {
            finalContent = String.valueOf(e.get("content"));
            cards = e.getOrDefault("cards", List.of());
          }
        }
      }
      if (finalContent == null) throw Kernel.error(502, "INCOMPLETE_STREAM");
      if (!delta.isEmpty()) emit(t, delta.toString());
      memoryChat.finish(t, finalContent, cards);
    } catch (Exception e) {
      String code = e instanceof Kernel.Problem p ? p.code : "AGENT_UNAVAILABLE";
      try {
        k.tx.executeWithoutResult(
            s -> {
              if (k.db.update(
                      "UPDATE turns SET status='FAILED',error_code=?,lease_until=NULL WHERE id=?"
                          + " AND epoch=? AND attempt_id=? AND status='RUNNING'",
                      code,
                      id,
                      t.get("epoch"),
                      t.get("attempt_id"))
                  == 1) {
                chat.event(conv, "turn.failed", Map.of("turn_id", id, "code", code));
                k.db.update(
                    "UPDATE outbox SET delivered_at=now() WHERE kind='turn.dispatch' AND"
                        + " resource_id=?",
                    id);
              }
            });
      } catch (Exception ignored) {
      }
    }
  }

  void emit(Map<String, Object> t, String text) {
    emit(t, text, "token.delta");
  }

  void emit(Map<String, Object> t, String text, String eventType) {
    k.tx.executeWithoutResult(
        s -> {
          var user =
              k.row("SELECT memory_revision FROM users WHERE id=? FOR SHARE", t.get("owner_id"));
          if (((Number) user.get("memory_revision")).longValue()
              != ((Number) t.get("memory_revision")).longValue())
            throw Kernel.error(409, "MEMORY_REVISION_CHANGED");
          k.row("SELECT id FROM conversations WHERE id=? FOR UPDATE", t.get("conversation_id"));
          int n =
              k.db.queryForObject(
                  "SELECT count(*) FROM turns WHERE id=? AND epoch=? AND attempt_id=? AND"
                      + " status='RUNNING' AND lease_until>clock_timestamp()",
                  Integer.class,
                  t.get("id"),
                  t.get("epoch"),
                  t.get("attempt_id"));
          if (n != 1) throw Kernel.error(409, "STALE_EXECUTION");
          chat.event(
              (UUID) t.get("conversation_id"),
              eventType,
              Map.of("turn_id", t.get("id"), "text", text));
        });
  }
}
