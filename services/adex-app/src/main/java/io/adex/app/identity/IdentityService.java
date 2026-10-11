package io.adex.app.identity;

import io.adex.kernel.Kernel;
import java.util.*;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;

/** Identity use cases. Guest promotion keeps the owner ID so history and files retain ownership. */
@Service
public class IdentityService {
  private final Kernel k;
  private final BCryptPasswordEncoder passwords = new BCryptPasswordEncoder(12);

  public IdentityService(Kernel k) {
    this.k = k;
  }

  public Map<String, Object> account(UUID id) {
    return k.row("SELECT username,is_guest FROM users WHERE id=?", id);
  }

  public Map<String, Object> me(UUID id) {
    return k.row("SELECT id,username,is_guest,memory_revision FROM users WHERE id=?", id);
  }

  public void logout(String token) {
    k.db.update("DELETE FROM sessions WHERE token_hash=?", Kernel.hash(token));
  }

  public void createGuest(UUID id, String username) {
    k.db.update(
        "INSERT INTO users(id,username,password_hash,is_guest,settings) VALUES(?,?, '!',true,'{\"memory_enabled\":false}'::jsonb)",
        id,
        username);
  }

  public IdentityPrincipal login(Map<String, Object> b, String clientAddress) {

    String username = Kernel.text(b, "username", 128), password = Kernel.text(b, "password", 256);
    String bucket = Kernel.hash(clientAddress + ":" + username);
    int count =
        k.db.queryForObject(
            "INSERT INTO login_limits(bucket,window_start,attempts)"
                + " VALUES(?,date_trunc('minute',now()),1) ON CONFLICT(bucket) DO UPDATE SET"
                + " attempts=CASE WHEN login_limits.window_start=date_trunc('minute',now()) THEN"
                + " login_limits.attempts+1 ELSE 1 END,window_start=date_trunc('minute',now())"
                + " RETURNING attempts",
            Integer.class,
            bucket);
    if (count > 10) throw Kernel.error(429, "LOGIN_RATE_LIMITED");
    var rows = k.db.queryForList("SELECT * FROM users WHERE username=?", username);
    String hash =
        rows.isEmpty()
            ? "$2a$12$F9AMygRTzNMkdZ72NMFN8eTHskPt.pGS6WRLfVZyC23xYeFLMFx8a"
            : String.valueOf(rows.getFirst().get("password_hash"));
    if (!passwords.matches(password, hash) || rows.isEmpty())
      throw Kernel.error(401, "INVALID_CREDENTIALS");
    if (Boolean.TRUE.equals(rows.getFirst().get("is_guest")))
      throw Kernel.error(401, "INVALID_CREDENTIALS");
    return new IdentityPrincipal((UUID) rows.getFirst().get("id"), username, false);
  }

  public IdentityPrincipal register(Map<String, Object> b, Optional<UUID> existingOwner) {

    String username = Kernel.text(b, "username", 32).toLowerCase(Locale.ROOT),
        password = Kernel.text(b, "password", 128);
    if (!username.matches("[a-z0-9][a-z0-9_-]{2,31}") || username.startsWith("guest_"))
      throw Kernel.error(400, "INVALID_USERNAME");

    UUID id = existingOwner.orElseGet(Kernel::id);
    String hash = passwords.encode(password);
    try {
      k.tx.executeWithoutResult(
          tx -> {
            var rows = k.db.queryForList("SELECT is_guest FROM users WHERE id=? FOR UPDATE", id);
            if (!rows.isEmpty()) {
              if (!Boolean.TRUE.equals(rows.getFirst().get("is_guest")))
                throw Kernel.error(409, "ALREADY_REGISTERED");
              k.db.update(
                  "UPDATE users SET username=?,password_hash=?,is_guest=false,settings=settings||'{\"memory_enabled\":true}'::jsonb WHERE id=?",
                  username,
                  hash,
                  id);
              k.db.update("DELETE FROM sessions WHERE owner_id=?", id);
            } else
              k.db.update(
                  "INSERT INTO users(id,username,password_hash) VALUES(?,?,?)", id, username, hash);
          });
    } catch (org.springframework.dao.DuplicateKeyException e) {
      throw Kernel.error(409, "USERNAME_TAKEN");
    }
    return new IdentityPrincipal(id, username, false);
  }
}
