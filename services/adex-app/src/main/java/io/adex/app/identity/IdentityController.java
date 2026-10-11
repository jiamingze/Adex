package io.adex.app.identity;

import io.adex.kernel.Kernel;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.util.*;
import java.util.concurrent.*;
import org.springframework.web.bind.annotation.*;

/** HTTP adapter for Identity operations. */
@RestController
public class IdentityController {
  private final Auth auth;
  private final IdentityService service;

  public IdentityController(Auth auth, IdentityService service) {
    this.auth = auth;
    this.service = service;
  }

  @PostMapping("/api/v1/auth/login")
  public Object login(
      @RequestBody Map<String, Object> b, HttpServletRequest r, HttpServletResponse response) {
    auth.checkOrigin(r);
    var principal = service.login(b, r.getRemoteAddr());
    return auth.issue(principal.id(), principal.username(), principal.guest(), response);
  }

  @PostMapping("/api/v1/auth/guest")
  public Object guest(HttpServletRequest r, HttpServletResponse response) {
    auth.checkOrigin(r);
    var existing = auth.sessionOwner(r);
    if (existing.isPresent()) {
      var user = service.account(existing.get());
      return Map.of(
          "token",
          auth.sessionToken(r),
          "username",
          user.get("username"),
          "is_guest",
          user.get("is_guest"));
    }
    auth.rate(r, "guest", 10);
    UUID id = Kernel.id();
    String username = "guest_" + id;
    service.createGuest(id, username);
    return auth.issue(id, username, true, response);
  }

  @PostMapping("/api/v1/auth/register")
  public Object register(
      @RequestBody Map<String, Object> b, HttpServletRequest r, HttpServletResponse response) {
    auth.checkOrigin(r);
    auth.rate(r, "register", 10);
    var principal = service.register(b, auth.sessionOwner(r));
    return auth.issue(principal.id(), principal.username(), principal.guest(), response);
  }

  @PostMapping("/api/v1/auth/logout")
  public Object logout(HttpServletRequest r, HttpServletResponse response) {
    response.addHeader(
        "Set-Cookie", "adex_session=; Path=/api/; HttpOnly; SameSite=Lax; Max-Age=0");
    service.logout(auth.sessionToken(r));
    return Map.of("ok", true);
  }

  @GetMapping("/api/v1/me")
  public Object me(HttpServletRequest r) {
    return service.me(auth.owner(r));
  }
}
