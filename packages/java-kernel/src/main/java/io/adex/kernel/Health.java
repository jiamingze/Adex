package io.adex.kernel;

import java.util.Map;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
public class Health {
  private final Kernel k;

  public Health(Kernel k) {
    this.k = k;
  }

  @GetMapping("/health/live")
  public Object live() {
    return Map.of("status", "UP", "service", k.service);
  }

  @GetMapping("/health/ready")
  public Object ready() {
    try {
      k.db.queryForObject("SELECT 1", Integer.class);
      return Map.of("status", "UP", "service", k.service);
    } catch (Exception e) {
      return ResponseEntity.status(503).body(Map.of("status", "DOWN"));
    }
  }
}
