package io.adex.app.memory;

import io.adex.app.identity.Auth;
import jakarta.servlet.http.HttpServletRequest;
import java.util.*;
import java.util.concurrent.*;
import org.springframework.web.bind.annotation.*;

/** HTTP adapter for Memory operations. */
@RestController
public class MemoryController {
  private final Auth auth;
  private final MemoryQueryService service;

  public MemoryController(Auth auth, MemoryQueryService service) {
    this.auth = auth;
    this.service = service;
  }

  @GetMapping("/api/v1/memories")
  public Object memories(HttpServletRequest r) {
    return service.memories(auth.owner(r));
  }

  @PostMapping("/api/v1/memories")
  public Object memory(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    return service.memory(auth.owner(r), b);
  }

  @DeleteMapping("/api/v1/memories/{id}")
  public Object forget(HttpServletRequest r, @PathVariable UUID id) {
    return service.forget(auth.owner(r), id);
  }

  @PatchMapping("/api/v1/memories/{id}")
  public Object correct(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> b) {
    return service.correct(auth.owner(r), id, b);
  }
}
