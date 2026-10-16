package io.adex.app.browser;

import io.adex.kernel.Kernel;
import java.util.*;
import org.springframework.stereotype.Service;

/** Owner-scoped browser application boundary; credentials never enter Agent calls. */
@Service
public class BrowserGateway {
  private final Kernel k;

  public BrowserGateway(Kernel k) {
    this.k = k;
  }

  public Object accounts(UUID owner) {
    return k.call("tools", "browser:read", owner, null, "GET", "/internal/browser/accounts", null);
  }

  public Object revokeAccount(UUID owner, UUID id) {
    var value =
        (Map<String, Object>)
            k.call(
                "tools",
                "browser:control",
                owner,
                id,
                "POST",
                "/internal/browser/accounts/" + id + "/revoke",
                Map.of());
    for (Object item : (List<?>) value.get("runs")) {
      UUID run = Kernel.uuid(item);
      k.call(
          "automation",
          "run:cancel",
          owner,
          run,
          "POST",
          "/internal/runs/" + run + "/cancel",
          Map.of());
    }
    return value;
  }

  public Object sessions(UUID owner) {
    return k.call("tools", "browser:read", owner, null, "GET", "/internal/browser/sessions", null);
  }

  public Object view(UUID owner, UUID id) {
    var value =
        new LinkedHashMap<String, Object>(
            (Map<String, Object>)
                k.call(
                    "tools",
                    "browser:read",
                    owner,
                    id,
                    "GET",
                    "/internal/browser/sessions/" + id,
                    null));
    UUID run = Kernel.uuid(value.get("run_id"));
    var current =
        (Map<String, Object>)
            k.call("automation", "run:read", owner, run, "GET", "/internal/runs/" + run, null);
    value.put("run_status", current.get("status"));
    return value;
  }

  public Object run(UUID owner, UUID id) {
    var run =
        (Map<String, Object>)
            k.call("automation", "run:read", owner, id, "GET", "/internal/runs/" + id, null);
    if (!"BROWSER".equals(run.get("kind"))) throw Kernel.error(400, "NOT_BROWSER_RUN");
    var lookup =
        (Map<String, Object>)
            k.call("tools", "browser:read", owner, id, "GET", "/internal/browser/runs/" + id, null);
    var result = new LinkedHashMap<String, Object>();
    result.put("is_guest", k.row("SELECT is_guest FROM users WHERE id=?", owner).get("is_guest"));
    result.put("run_id", id);
    result.put("conversation_id", run.get("origin_conversation_id"));
    result.put("status", run.get("status"));
    result.put("error_code", run.get("error_code"));
    result.put("result", run.get("result"));
    result.put("session", lookup.get("session"));
    if (lookup.get("session") instanceof Map<?, ?> session && session.get("action_id") != null) {
      UUID action = Kernel.uuid(session.get("action_id"));
      result.put(
          "action",
          k.call(
              "tools", "approval:read", owner, action, "GET", "/internal/actions/" + action, null));
    }
    return result;
  }

  public Object control(UUID owner, UUID id, Map<String, Object> body) {
    if (Boolean.TRUE.equals(
        k.row("SELECT is_guest FROM users WHERE id=?", owner).get("is_guest"))) {
      if ("remember".equals(body.get("action"))) throw Kernel.error(403, "SIGN_IN_REQUIRED");
      body = new LinkedHashMap<>(body);
      body.put("remember_login", false);
    }
    boolean login = "secure_login".equals(body.get("action"));
    if (login) {
      var before = (Map<String, Object>) view(owner, id);
      if (!"WAITING_INPUT".equals(before.get("run_status")))
        throw Kernel.error(409, "BROWSER_AGENT_STILL_PAUSING");
    }
    var value =
        (Map<String, Object>)
            k.call(
                "tools",
                "browser:control",
                owner,
                id,
                "POST",
                "/internal/browser/sessions/" + id + "/control",
                body);
    if (login && value.get("login_form") == null) {
      // Submission is not login proof. Resume the original Run to inspect the actual
      // page; MFA or a rejected login hands control back without claiming success.
      var result = new LinkedHashMap<String, Object>(value);
      if (Boolean.TRUE.equals(body.get("remember_login"))) {
        try {
          var uri = java.net.URI.create(String.valueOf(value.get("url")));
          String origin = uri.getScheme() + "://" + uri.getRawAuthority();
          if (origin.equals(body.get("origin"))) {
            control(
                owner,
                id,
                Map.of(
                    "action",
                    "remember",
                    "profile_revision",
                    body.getOrDefault("profile_revision", 0)));
            result.put("remembered", true);
          } else result.put("remembered", false);
        } catch (Kernel.Problem changed) {
          result.put("remembered", false);
        }
      }
      resume(owner, id);
      result.put("auto_resumed", true);
      return result;
    }
    return value;
  }

  public Object resume(UUID owner, UUID id) {
    var value = (Map<String, Object>) view(owner, id);
    UUID run = Kernel.uuid(value.get("run_id"));
    var current =
        (Map<String, Object>)
            k.call("automation", "run:read", owner, run, "GET", "/internal/runs/" + run, null);
    if (Set.of("QUEUED", "RUNNING").contains(current.get("status"))
        && "AGENT".equals(value.get("status"))) return current;
    if (!"WAITING_INPUT".equals(current.get("status")))
      throw Kernel.error(409, "BROWSER_AGENT_STILL_PAUSING");
    control(owner, id, Map.of("action", "resume"));
    return k.call(
        "automation",
        "run:resume",
        owner,
        run,
        "POST",
        "/internal/runs/" + run + "/resume",
        Map.of());
  }

  public Object close(UUID owner, UUID id) {
    var sessions = (Map<String, Object>) sessions(owner);
    var rows = (List<Map<String, Object>>) sessions.get("items");
    var row =
        rows.stream()
            .filter(x -> id.toString().equals(String.valueOf(x.get("id"))))
            .findFirst()
            .orElseThrow(() -> Kernel.error(404, "BROWSER_SESSION_NOT_FOUND"));
    var result =
        k.call(
            "tools",
            "browser:control",
            owner,
            id,
            "POST",
            "/internal/browser/sessions/" + id + "/close",
            Map.of());
    UUID run = Kernel.uuid(row.get("run_id"));
    k.call(
        "automation",
        "run:cancel",
        owner,
        run,
        "POST",
        "/internal/runs/" + run + "/cancel",
        Map.of());
    return result;
  }
}
