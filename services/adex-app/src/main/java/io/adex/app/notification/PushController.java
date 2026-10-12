package io.adex.app.notification;

import io.adex.app.identity.Auth;
import jakarta.servlet.http.HttpServletRequest;
import java.util.*;
import org.springframework.web.bind.annotation.*;

@RestController
public class PushController {
  private final Auth auth;
  private final PushService service;

  public PushController(Auth auth, PushService service) {
    this.auth = auth;
    this.service = service;
  }

  @PostMapping("/api/v1/push/devices")
  public Object register(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    return service.register(auth.owner(r), b);
  }

  @DeleteMapping("/api/v1/push/devices/{id}")
  public Object revoke(HttpServletRequest r, @PathVariable UUID id) {
    return service.revoke(auth.owner(r), id);
  }
}
