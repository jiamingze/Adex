package io.adex.automation.schedule;

import io.adex.kernel.Kernel;
import jakarta.servlet.http.HttpServletRequest;
import java.time.*;
import java.util.*;
import org.springframework.web.bind.annotation.*;

/** Transport for Schedule; authorization precedes every state transition. */
@RestController
public class ScheduleController {
  private final Kernel k;
  private final ScheduleService service;

  public ScheduleController(Kernel k, ScheduleService service) {
    this.k = k;
    this.service = service;
  }

  @GetMapping("/internal/automations")
  public Object list(HttpServletRequest r) {
    return service.list(k.require(r, "app", "schedule:read", null));
  }

  @PostMapping("/internal/automations")
  public Object create(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    return service.create(k.require(r, "app", "schedule:write", null), b);
  }

  @PatchMapping("/internal/automations/{id}")
  public Object update(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> b) {
    return service.update(k.require(r, "app", "schedule:write", id), id, b);
  }
}
