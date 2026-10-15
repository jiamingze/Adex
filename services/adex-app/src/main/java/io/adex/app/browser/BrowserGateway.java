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

  public Object control(UUID owner, UUID id, Map<String, Object> body) {
    return k.call(
        "tools",
        "browser:control",
        owner,
        id,
        "POST",
        "/internal/browser/sessions/" + id + "/control",
        body);
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
