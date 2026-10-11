package io.adex.app.notification;

import io.adex.app.identity.Auth;
import jakarta.servlet.http.HttpServletRequest;
import java.util.*;
import java.util.concurrent.*;
import org.springframework.web.bind.annotation.*;

/** HTTP adapter for Notification operations. */
@RestController
public class NotificationController {
  private final Auth auth;
  private final NotificationService service;

  public NotificationController(Auth auth, NotificationService service) {
    this.auth = auth;
    this.service = service;
  }

  @GetMapping("/api/v1/notifications")
  public Object notifications(HttpServletRequest r) {
    return service.notifications(auth.owner(r));
  }

  @PostMapping("/api/v1/notifications/{id}/read")
  public Object read(HttpServletRequest r, @PathVariable UUID id) {
    return service.read(auth.owner(r), id);
  }
}
