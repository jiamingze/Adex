package io.adex.automation.run;

import io.adex.kernel.Kernel;
import jakarta.servlet.http.HttpServletRequest;
import java.time.*;
import java.util.*;
import org.springframework.web.bind.annotation.*;

/** Transport for RunExecution; authorization precedes every state transition. */
@RestController
public class RunExecutionController {
  private final Kernel k;
  private final RunExecutionService service;

  public RunExecutionController(Kernel k, RunExecutionService service) {
    this.k = k;
    this.service = service;
  }

  @PostMapping("/internal/runs/claim")
  public Object claim(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    return service.claim(k.require(r, "agent", "run:claim", null), b);
  }

  @PostMapping("/internal/runs/{id}/authorize-effect")
  public Object authorizeEffect(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> b) {
    return service.authorizeEffect(k.require(r, "tools", "effect:execute", id), id, b);
  }

  @PostMapping("/internal/runs/{id}/heartbeat")
  public Object heartbeat(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> b) {
    return service.heartbeat(k.require(r, "agent", "run:write", id), id, b);
  }

  @PostMapping("/internal/runs/{id}/checkpoint")
  public Object checkpoint(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> b) {
    return service.checkpoint(k.require(r, "agent", "run:write", id), id, b);
  }

  @PostMapping("/internal/runs/{id}/suspend")
  public Object suspend(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> b) {
    return service.suspend(k.require(r, "agent", "run:write", id), id, b);
  }

  @PostMapping("/internal/runs/{id}/complete")
  public Object complete(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> b) {
    return service.complete(k.require(r, "agent", "run:write", id), id, b);
  }

  @PostMapping("/internal/runs/{id}/fail")
  public Object fail(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> b) {
    return service.fail(k.require(r, "agent", "run:write", id), id, b);
  }

  @GetMapping("/internal/runs/{id}/checkpoint-refs")
  public Object checkpointRefs(HttpServletRequest request, @PathVariable UUID id) {
    return service.checkpointRefs(k.require(request, "agent", "run:inspect", id), id);
  }
}
