package io.adex.app.proactive;

import io.adex.app.identity.Auth;
import jakarta.servlet.http.HttpServletRequest;
import java.util.*;
import org.springframework.web.bind.annotation.*;

@RestController
public class ProactiveController {
  private final Auth auth;
  private final ProactiveService service;

  public ProactiveController(Auth auth, ProactiveService service) {
    this.auth = auth;
    this.service = service;
  }

  @GetMapping("/api/v1/signals")
  public Object list(
      HttpServletRequest r, @RequestParam(defaultValue = "false") boolean include_closed) {
    return service.list(auth.owner(r), include_closed);
  }

  @PatchMapping("/api/v1/signals/{id}")
  public Object feedback(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> body) {
    return service.feedback(auth.owner(r), id, body);
  }
}
