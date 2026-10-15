package io.adex.app.browser;

import io.adex.app.identity.Auth;
import jakarta.servlet.http.*;
import java.util.*;
import org.springframework.web.bind.annotation.*;

/** Thin authenticated adapter. Do not log secure-input bodies or cache screenshots. */
@RestController
public class BrowserController {
  private final Auth auth;
  private final BrowserGateway browser;

  public BrowserController(Auth auth, BrowserGateway browser) {
    this.auth = auth;
    this.browser = browser;
  }

  @GetMapping("/api/v1/browser/runs/{id}")
  public Object run(HttpServletRequest r, HttpServletResponse response, @PathVariable UUID id) {
    response.setHeader("Cache-Control", "no-store");
    return browser.run(auth.owner(r), id);
  }

  @GetMapping("/api/v1/browser/accounts")
  public Object accounts(HttpServletRequest r) {
    return browser.accounts(auth.owner(r));
  }

  @PostMapping("/api/v1/browser/accounts/{id}/revoke")
  public Object revokeAccount(HttpServletRequest r, @PathVariable UUID id) {
    return browser.revokeAccount(auth.owner(r), id);
  }

  @GetMapping("/api/v1/browser/sessions")
  public Object sessions(HttpServletRequest r) {
    return browser.sessions(auth.owner(r));
  }

  @GetMapping("/api/v1/browser/sessions/{id}")
  public Object view(HttpServletRequest r, HttpServletResponse response, @PathVariable UUID id) {
    response.setHeader("Cache-Control", "no-store");
    return browser.view(auth.owner(r), id);
  }

  @PostMapping("/api/v1/browser/sessions/{id}/control")
  public Object control(
      HttpServletRequest r,
      HttpServletResponse response,
      @PathVariable UUID id,
      @RequestBody Map<String, Object> b) {
    response.setHeader("Cache-Control", "no-store");
    return browser.control(auth.owner(r), id, b);
  }

  @PostMapping("/api/v1/browser/sessions/{id}/resume")
  public Object resume(HttpServletRequest r, @PathVariable UUID id) {
    return browser.resume(auth.owner(r), id);
  }

  @PostMapping("/api/v1/browser/sessions/{id}/close")
  public Object close(HttpServletRequest r, @PathVariable UUID id) {
    return browser.close(auth.owner(r), id);
  }
}
