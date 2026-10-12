package io.adex.app.productivity;

import io.adex.app.identity.Auth;
import jakarta.servlet.http.HttpServletRequest;
import java.util.*;
import org.springframework.web.bind.annotation.*;

@RestController
public class MatrixController {
  private final Auth auth;
  private final MatrixService service;

  public MatrixController(Auth auth, MatrixService service) {
    this.auth = auth;
    this.service = service;
  }

  @GetMapping("/api/v1/matrix")
  public Object list(HttpServletRequest r) {
    return service.list(auth.owner(r));
  }

  @PostMapping("/api/v1/matrix")
  public Object create(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    return service.save(auth.owner(r), null, b);
  }

  @PatchMapping("/api/v1/matrix/{id}")
  public Object update(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> b) {
    return service.save(auth.owner(r), id, b);
  }

  @DeleteMapping("/api/v1/matrix/{id}")
  public Object delete(HttpServletRequest r, @PathVariable UUID id) {
    return service.delete(auth.owner(r), id);
  }
}
