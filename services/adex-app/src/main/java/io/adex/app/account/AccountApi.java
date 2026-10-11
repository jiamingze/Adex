package io.adex.app.account;

import io.adex.app.identity.Auth;
import jakarta.servlet.http.HttpServletRequest;
import java.util.*;
import org.springframework.web.bind.annotation.*;

@RestController
public class AccountApi {
  private final Auth auth;
  private final AccountService service;

  public AccountApi(Auth auth, AccountService service) {
    this.auth = auth;
    this.service = service;
  }

  @GetMapping("/api/v1/settings")
  public Object settings(HttpServletRequest r) {
    return service.settings(auth.owner(r));
  }

  @PatchMapping("/api/v1/settings")
  public Object save(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    return service.save(auth.owner(r), b);
  }

  @GetMapping("/api/v1/usage")
  public Object usage(HttpServletRequest r) {
    return service.usage(auth.owner(r));
  }

  @PostMapping("/api/v1/security/revoke-sessions")
  public Object revoke(HttpServletRequest r) {
    return service.revoke(auth.owner(r), auth.sessionToken(r));
  }
}
