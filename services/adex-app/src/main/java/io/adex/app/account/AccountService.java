package io.adex.app.account;

import io.adex.kernel.Kernel;
import java.util.*;
import org.springframework.stereotype.Service;

/** Owns Account use cases; HTTP authentication is performed by the adapter. */
@Service
public class AccountService {
  private final Kernel k;

  public AccountService(Kernel k) {
    this.k = k;
  }

  public Object settings(UUID owner) {
    return k.row("SELECT username,settings FROM users WHERE id=?", owner);
  }

  public Object save(UUID owner, Map<String, Object> b) {
    for (String key : b.keySet())
      if (!Set.of("memory_enabled", "email_notifications", "email").contains(key))
        throw Kernel.error(400, "INVALID_SETTING");
    for (String key : List.of("memory_enabled", "email_notifications"))
      if (b.containsKey(key) && !(b.get(key) instanceof Boolean))
        throw Kernel.error(400, "INVALID_SETTING");
    if (b.containsKey("email") && !(b.get("email") instanceof String))
      throw Kernel.error(400, "INVALID_EMAIL");
    if (b.containsKey("email")
        && !String.valueOf(b.get("email")).isEmpty()
        && !String.valueOf(b.get("email")).matches("[^\\s@]{1,80}@[^\\s@]{1,120}\\.[^\\s@]{2,20}"))
      throw Kernel.error(400, "INVALID_EMAIL");
    return k.row(
        "UPDATE users SET settings=settings||?::jsonb WHERE id=? RETURNING settings",
        k.encode(b),
        owner);
  }

  public Object usage(UUID owner) {
    var result = new LinkedHashMap<String, Object>();
    result.put(
        "storage",
        k.row(
            "SELECT COALESCE(sum(size_bytes),0) AS used_bytes,262144000 AS quota_bytes FROM files WHERE owner_id=? AND status<>'DELETED'",
            owner));
    for (String service : List.of("agent", "tools")) {
      try {
        result.put(
            service.equals("agent") ? "model" : "tools",
            k.call(service, "usage:read", owner, null, "GET", "/internal/usage", null));
      } catch (Exception e) {
        result.put(service.equals("agent") ? "model" : "tools", Map.of("status", "UNAVAILABLE"));
      }
    }
    return result;
  }

  public Object revoke(UUID owner, String sessionToken) {
    String current = Kernel.hash(sessionToken);
    k.db.update("DELETE FROM sessions WHERE owner_id=? AND token_hash<>?", owner, current);
    return Map.of("ok", true);
  }
}
