package io.adex.automation.run;

import io.adex.kernel.Kernel;
import jakarta.servlet.http.HttpServletRequest;
import java.time.*;
import java.util.*;
import org.springframework.web.bind.annotation.*;

/** Transport for Run; authorization precedes every state transition. */
@RestController
public class RunController {
  private final Kernel k;
  private final RunService service;

  public RunController(Kernel k, RunService service) {
    this.k = k;
    this.service = service;
  }

  @PostMapping("/internal/tasks")
  public Object task(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    return service.task(k.require(r, "app", "task:write", null), b);
  }

  @GetMapping("/internal/runs")
  public Object runs(HttpServletRequest r) {
    return service.runs(k.require(r, "app", "run:read", null));
  }

  @PostMapping("/internal/runs/{id}/cancel")
  public Object cancel(HttpServletRequest r, @PathVariable UUID id) {
    return service.cancel(k.require(r, "app", "run:cancel", id), id);
  }
}
