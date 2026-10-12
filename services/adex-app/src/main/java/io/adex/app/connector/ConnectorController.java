package io.adex.app.connector;

import io.adex.app.identity.Auth;
import io.adex.kernel.Kernel;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.util.*;
import org.springframework.web.bind.annotation.*;

@RestController
public class ConnectorController {
  private final Auth auth;
  private final ConnectorGateway service;

  public ConnectorController(Auth auth, ConnectorGateway service) {
    this.auth = auth;
    this.service = service;
  }

  @GetMapping("/api/v1/connectors")
  public Object list(HttpServletRequest r) {
    return service.list(auth.owner(r));
  }

  @PostMapping("/api/v1/connectors/google/authorize")
  public Object authorize(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    return service.authorize(auth.owner(r), Kernel.hash(auth.sessionToken(r)), b);
  }

  @GetMapping("/api/v1/connectors/google/callback")
  public Object callback(
      HttpServletRequest r,
      HttpServletResponse response,
      @RequestParam String state,
      @RequestParam String code) {
    Object result = service.callback(auth.owner(r), Kernel.hash(auth.sessionToken(r)), state, code);
    if (r.getHeader("Accept") != null && r.getHeader("Accept").contains("text/html")) {
      String base = Kernel.env("ADEX_PUBLIC_WEB_URL", "http://127.0.0.1:5173");
      if (!base.startsWith("https://") && !base.equals("http://127.0.0.1:5173"))
        throw Kernel.error(503, "PUBLIC_WEB_URL_NOT_CONFIGURED");
      response.setStatus(303);
      response.setHeader("Location", base + "/?connected=1");
    }
    return result;
  }

  @PostMapping("/api/v1/connectors/{id}/{action}")
  public Object connection(
      HttpServletRequest r,
      @PathVariable UUID id,
      @PathVariable String action,
      @RequestBody Map<String, Object> b) {
    if (action.equals("watch")) return service.watch(auth.owner(r), id, b);
    return action.equals("sync")
        ? service.sync(auth.owner(r), id, b)
        : service.connection(auth.owner(r), id, action, b);
  }

  @GetMapping("/api/v1/actions")
  public Object actions(HttpServletRequest r) {
    return service.actions(auth.owner(r));
  }

  @PostMapping("/api/v1/actions")
  public Object draft(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    return service.draft(auth.owner(r), b);
  }

  @PostMapping("/api/v1/actions/{id}/{decision}")
  public Object decide(
      HttpServletRequest r,
      @PathVariable UUID id,
      @PathVariable String decision,
      @RequestBody Map<String, Object> b) {
    return service.decide(auth.owner(r), id, decision, b);
  }
}
