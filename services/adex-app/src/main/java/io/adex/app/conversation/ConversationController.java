package io.adex.app.conversation;

import io.adex.app.identity.Auth;
import io.adex.kernel.Kernel;
import jakarta.servlet.http.HttpServletRequest;
import java.util.*;
import java.util.concurrent.*;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

/** HTTP adapter for Conversation operations. */
@RestController
public class ConversationController {
  private final Kernel k;
  private final ConversationService service;
  private final Auth auth;
  private final ConversationStore chat;

  public ConversationController(
      Kernel k, Auth auth, ConversationStore chat, ConversationService service) {
    this.service = service;
    this.k = k;
    this.auth = auth;
    this.chat = chat;
  }

  @GetMapping("/api/v1/conversations")
  public Object conversations(
      HttpServletRequest r, @RequestParam(defaultValue = "2100-01-01T00:00:00Z") String before) {
    return service.conversations(auth.owner(r), before);
  }

  @PostMapping("/api/v1/conversations")
  public Object create(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    return service.create(auth.owner(r), b);
  }

  @GetMapping("/api/v1/conversations/{id}/messages")
  public Object messages(
      HttpServletRequest r,
      @PathVariable UUID id,
      @RequestParam(defaultValue = "0") long after_seq,
      @RequestParam(defaultValue = "100") int limit,
      @RequestParam(defaultValue = "false") boolean latest) {
    return service.messages(auth.owner(r), id, after_seq, limit, latest);
  }

  @PostMapping("/api/v1/conversations/{id}/messages")
  public Object send(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> b) {
    return service.send(auth.owner(r), id, b);
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

  @PatchMapping("/api/v1/conversations/{id}")
  public Object rename(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> b) {
    return service.rename(auth.owner(r), id, b);
  }

  @DeleteMapping("/api/v1/conversations/{id}")
  public Object delete(HttpServletRequest r, @PathVariable UUID id) {
    return service.delete(auth.owner(r), id);
  }

  @PostMapping("/api/v1/conversations/{id}/stop")
  public Object stop(HttpServletRequest r, @PathVariable UUID id) {
    return service.stop(auth.owner(r), id);
  }

  @GetMapping("/api/v1/search")
  public Object search(HttpServletRequest r, @RequestParam String q) {
    return service.search(auth.owner(r), q);
  }
}
