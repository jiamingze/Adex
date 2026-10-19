package io.adex.app.productivity;

import io.adex.app.identity.Auth;
import jakarta.servlet.http.HttpServletRequest;
import java.util.*;
import org.springframework.web.bind.annotation.*;

@RestController
public class GoalController {
  private final Auth auth;
  private final GoalService goals;

  public GoalController(Auth auth, GoalService goals) {
    this.auth = auth;
    this.goals = goals;
  }

  @GetMapping("/api/v1/goals")
  public Object list(HttpServletRequest r) {
    return goals.list(auth.owner(r));
  }

  @PostMapping("/api/v1/goals")
  public Object create(HttpServletRequest r, @RequestBody Map<String, Object> body) {
    return goals.create(auth.owner(r), body);
  }

  @PatchMapping("/api/v1/goals/{id}")
  public Object update(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> body) {
    return goals.update(auth.owner(r), id, body);
  }

  @PostMapping("/api/v1/goals/plan")
  public Object plan(HttpServletRequest r, @RequestBody Map<String, Object> body) {
    return goals.plan(auth.owner(r), body);
  }
}
