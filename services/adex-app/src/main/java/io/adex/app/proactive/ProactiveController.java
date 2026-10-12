package io.adex.app.proactive;

import io.adex.app.identity.Auth;
import jakarta.servlet.http.HttpServletRequest;
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
  public Object list(HttpServletRequest r) {
    return service.list(auth.owner(r));
  }
}
