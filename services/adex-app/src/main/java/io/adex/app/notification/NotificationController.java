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
  private final NotificationPreferences preferences;

  public NotificationController(
      Auth auth, NotificationService service, NotificationPreferences preferences) {
    this.auth = auth;
    this.service = service;
    this.preferences = preferences;
  }

  @GetMapping("/api/v1/notifications")
  public Object notifications(HttpServletRequest r) {
    return service.notifications(auth.owner(r));
  }

  @GetMapping("/api/v1/notifications/{id}/resume")
  public Object resume(
      HttpServletRequest r,
      @PathVariable UUID id,
      @RequestParam(defaultValue = "true") boolean include_run) {
    return service.resume(auth.owner(r), id, include_run);
  }

  @GetMapping("/api/v1/notification-preferences")
  public Object preferences(HttpServletRequest r) {
    return preferences.get(auth.owner(r));
  }

  @PutMapping("/api/v1/notification-preferences")
  public Object savePreferences(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    return preferences.save(auth.owner(r), b);
  }

  @PostMapping("/api/v1/notifications/{id}/read")
  public Object read(HttpServletRequest r, @PathVariable UUID id) {
    return service.read(auth.owner(r), id);
  }
}
