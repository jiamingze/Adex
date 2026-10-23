package io.adex.app.conversation;

import io.adex.kernel.Kernel;
import jakarta.servlet.http.HttpServletRequest;
import java.util.*;
import java.util.concurrent.*;
import org.springframework.web.bind.annotation.*;

/** HTTP adapter for Context operations. */
@RestController
public class ContextController {
  private final Kernel k;
  private final ConversationStore chat;

  public ContextController(Kernel k, ConversationStore chat) {
    this.k = k;
    this.chat = chat;
  }

  /** Desktop dispatch rechecks App ownership; deleted conversations cannot authorize a command. */
  @GetMapping("/internal/conversations/{id}/computer-access")
  public Object computerAccess(HttpServletRequest r, @PathVariable UUID id) {
    var claims = k.require(r, "tools", "computer:access", id);
    chat.own(Kernel.uuid(claims.get("owner")), id);
    return Map.of("allowed", true);
  }

  @GetMapping("/internal/context/{id}")
  public Object context(
      HttpServletRequest r,
      @PathVariable UUID id,
      @RequestParam(defaultValue = "9223372036854775807") long up_to_seq) {
    var claims = k.require(r, "agent", "context:read", id);
    return chat.context(Kernel.uuid(claims.get("owner")), id, up_to_seq);
  }
}
