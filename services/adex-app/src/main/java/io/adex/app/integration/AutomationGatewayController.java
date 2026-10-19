package io.adex.app.integration;

import io.adex.app.identity.Auth;
import jakarta.servlet.http.HttpServletRequest;
import java.util.*;
import java.util.concurrent.*;
import org.springframework.web.bind.annotation.*;

/** HTTP adapter for AutomationGateway operations. */
@RestController
public class AutomationGatewayController {
  private final Auth auth;
  private final AutomationGateway service;

  public AutomationGatewayController(Auth auth, AutomationGateway service) {
    this.auth = auth;
    this.service = service;
  }

  @GetMapping("/api/v1/automations")
  public Object schedules(HttpServletRequest r) {
    return service.schedules(auth.owner(r));
  }

  @PostMapping("/api/v1/automations")
  public Object schedule(
      HttpServletRequest r,
      @RequestBody Map<String, Object> b,
      @RequestHeader("Idempotency-Key") String key) {
    return service.schedule(auth.owner(r), b, key);
  }

  @PatchMapping("/api/v1/automations/{id}")
  public Object update(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> b) {
    return service.update(auth.owner(r), id, b);
  }

  @DeleteMapping("/api/v1/automations/{id}")
  public Object delete(HttpServletRequest r, @PathVariable UUID id, @RequestParam long revision) {
    return service.delete(auth.owner(r), id, revision);
  }

  @PostMapping("/api/v1/tasks")
  public Object createTask(
      HttpServletRequest r,
      @RequestBody Map<String, Object> body,
      @RequestHeader("Idempotency-Key") String key) {
    return service.createTask(auth.owner(r), body, key);
  }

  @GetMapping("/api/v1/tasks")
  public Object tasks(HttpServletRequest r) {
    return service.tasks(auth.owner(r));
  }

  @PostMapping("/api/v1/tasks/{id}/cancel")
  public Object cancel(HttpServletRequest r, @PathVariable UUID id) {
    return service.cancel(auth.owner(r), id);
  }

  @GetMapping("/api/v1/monitors")
  public Object monitors(HttpServletRequest r) {
    return service.monitors(auth.owner(r));
  }

  @PostMapping("/api/v1/monitors")
  public Object monitor(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    return service.monitor(auth.owner(r), b);
  }

  @DeleteMapping("/api/v1/monitors/{id}")
  public Object cancelMonitor(HttpServletRequest r, @PathVariable UUID id) {
    return service.cancelMonitor(auth.owner(r), id);
  }

  @PostMapping("/api/v1/automations/draft")
  public Object draft(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    return service.draft(auth.owner(r), b);
  }
}
