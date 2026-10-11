package io.adex.app.integration;

import io.adex.app.conversation.ConversationStore;
import io.adex.app.identity.Auth;
import io.adex.kernel.Kernel;
import jakarta.servlet.http.HttpServletRequest;
import java.util.*;
import org.springframework.web.bind.annotation.*;

@RestController
public class ToolsApi {
  final Kernel k;
  final Auth auth;
  final ConversationStore chat;

  public ToolsApi(Kernel k, Auth auth, ConversationStore chat) {
    this.k = k;
    this.auth = auth;
    this.chat = chat;
  }

  @PostMapping("/api/v1/music/search")
  public Object music(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    return k.call("tools", "music:read", auth.owner(r), null, "POST", "/internal/music/search", b);
  }

  @GetMapping("/api/v1/approvals")
  public Object approvals(HttpServletRequest r) {
    return k.call(
        "tools", "approval:read", auth.owner(r), null, "GET", "/internal/approvals", null);
  }

  @PostMapping("/api/v1/approvals")
  public Object approval(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    UUID owner = auth.owner(r);
    chat.own(owner, Kernel.uuid(b.get("origin_conversation_id")));
    return k.call("tools", "approval:write", owner, null, "POST", "/internal/approvals", b);
  }

  @PostMapping("/api/v1/approvals/{id}/{action}")
  public Object act(HttpServletRequest r, @PathVariable UUID id, @PathVariable String action) {
    if (!Set.of("approve", "revoke", "reconcile").contains(action))
      throw Kernel.error(400, "INVALID_ACTION");
    UUID owner = auth.owner(r);
    var result =
        k.call(
            "tools",
            "approval:write",
            owner,
            id,
            "POST",
            "/internal/approvals/" + id + "/" + action,
            Map.of());
    if (action.equals("approve")) {
      var request = (Map<?, ?>) result.get("request");
      if (request == null) return result;
      UUID conv = Kernel.uuid(request.get("origin_conversation_id"));
      chat.own(owner, conv);
      return k.call(
          "automation",
          "task:write",
          owner,
          null,
          "POST",
          "/internal/tasks",
          Map.of(
              "kind",
              "CALENDAR",
              "instruction",
              "执行用户明确批准的日历草稿",
              "approval_id",
              id,
              "origin_conversation_id",
              conv,
              "idempotency_key",
              "approval:" + id));
    }
    return result;
  }
}
