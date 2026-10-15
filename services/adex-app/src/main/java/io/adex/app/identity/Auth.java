package io.adex.app.identity;

import io.adex.kernel.Kernel;
import jakarta.annotation.PostConstruct;
import jakarta.servlet.*;
import jakarta.servlet.http.*;
import java.io.IOException;
import java.time.*;
import java.util.*;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
public class Auth extends OncePerRequestFilter {
  private final Kernel k;
  private final BCryptPasswordEncoder passwords = new BCryptPasswordEncoder(12);

  public Auth(Kernel k) {
    this.k = k;
  }

  @PostConstruct
  void bootstrap() {
    String user = Kernel.env("ADEX_OWNER_USERNAME"), pass = Kernel.env("ADEX_OWNER_PASSWORD");
    if (pass.length() < 12
        && !Boolean.parseBoolean(Kernel.env("ADEX_ALLOW_SIMPLE_OWNER_PASSWORD", "false")))
      throw new IllegalStateException("Owner password must have at least 12 characters");
    k.db.update(
        "INSERT INTO users(id,username,password_hash) VALUES(?,?,?) ON CONFLICT(username) DO"
            + " NOTHING",
        Kernel.id(),
        user,
        passwords.encode(pass));
  }

  public UUID owner(HttpServletRequest r) {
    return (UUID) r.getAttribute("owner");
  }

  public String sessionToken(HttpServletRequest r) {
    String header = r.getHeader("Authorization");
    if (header != null && header.startsWith("Bearer ")) return header.substring(7);
    if (r.getCookies() != null)
      for (Cookie c : r.getCookies()) if (c.getName().equals("adex_session")) return c.getValue();
    return "";
  }

  public void checkOrigin(HttpServletRequest r) {
    String origin = r.getHeader("Origin");
    if (origin != null
        && !Arrays.asList(Kernel.env("ADEX_ALLOWED_ORIGINS", "capacitor://localhost").split(","))
            .contains(origin)) {
      try {
        if (!java.net.URI.create(origin).getRawAuthority().equals(r.getHeader("Host")))
          throw Kernel.error(403, "ORIGIN_DENIED");
      } catch (IllegalArgumentException e) {
        throw Kernel.error(403, "ORIGIN_DENIED");
      }
    }
  }

  public Optional<UUID> sessionOwner(HttpServletRequest r) {
    var rows =
        k.db.queryForList(
            "SELECT owner_id FROM sessions WHERE token_hash=? AND expires_at>clock_timestamp()",
            Kernel.hash(sessionToken(r)));
    return rows.isEmpty() ? Optional.empty() : Optional.of((UUID) rows.getFirst().get("owner_id"));
  }

  public Object issue(UUID owner, String username, boolean guest, HttpServletResponse response) {
    String token = Kernel.id().toString() + Kernel.id();
    int seconds = guest ? 2592000 : 43200;
    k.db.update(
        "INSERT INTO sessions(token_hash,owner_id,expires_at) VALUES(?,?,now()+(? * interval '1 second'))",
        Kernel.hash(token),
        owner,
        seconds);
    boolean secure = Boolean.parseBoolean(Kernel.env("ADEX_COOKIE_SECURE", "false"));
    response.addHeader(
        "Set-Cookie",
        "adex_session="
            + token
            + "; Path=/api/; HttpOnly; SameSite=Lax; Max-Age="
            + seconds
            + (secure ? "; Secure" : ""));
    return Map.of("token", token, "username", username, "is_guest", guest, "expires_in", seconds);
  }

  public void rate(HttpServletRequest r, String name, int max) {
    int count =
        k.db.queryForObject(
            "INSERT INTO login_limits(bucket,window_start,attempts) VALUES(?,date_trunc('hour',now()),1) ON CONFLICT(bucket) DO UPDATE SET attempts=CASE WHEN login_limits.window_start=date_trunc('hour',now()) THEN login_limits.attempts+1 ELSE 1 END,window_start=date_trunc('hour',now()) RETURNING attempts",
            Integer.class,
            Kernel.hash(name + ":" + r.getRemoteAddr()));
    if (count > max) throw Kernel.error(429, "AUTH_RATE_LIMITED");
  }

  @Override
  protected void doFilterInternal(
      HttpServletRequest req, HttpServletResponse res, FilterChain chain)
      throws ServletException, IOException {
    res.setHeader("Cache-Control", "no-store");
    res.setHeader("X-Content-Type-Options", "nosniff");
    if (req.getContentLengthLong()
        > ((req.getRequestURI().equals("/api/v1/files")
                || req.getRequestURI().equals("/internal/files"))
            ? 26L * 1024 * 1024
            : 262144)) {
      res.setStatus(413);
      res.getWriter().write("{\"code\":\"REQUEST_TOO_LARGE\"}");
      return;
    }
    if (req.getMethod().equals("OPTIONS")) {
      chain.doFilter(req, res);
      return;
    }
    if (req.getRequestURI().startsWith("/api/v1/")
        && !Set.of("/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/guest")
            .contains(req.getRequestURI())
        && !req.getRequestURI().startsWith("/api/v1/media/")
        && !(req.getMethod().equals("GET")
            && req.getRequestURI().startsWith("/api/v1/previews/"))) {
      try {
        String a = sessionToken(req);
        var rows =
            a.isEmpty()
                ? List.<Map<String, Object>>of()
                : k.db.queryForList(
                    "SELECT s.owner_id,u.is_guest FROM sessions s JOIN users u ON u.id=s.owner_id WHERE s.token_hash=? AND s.expires_at>clock_timestamp()",
                    Kernel.hash(a));
        if (req.getHeader("Authorization") == null
            && !Set.of("GET", "HEAD").contains(req.getMethod())) checkOrigin(req);
        if (rows.isEmpty()) {
          res.setStatus(401);
          res.setContentType("application/json");
          res.getWriter().write("{\"code\":\"UNAUTHENTICATED\"}");
          return;
        }
        req.setAttribute("owner", rows.getFirst().get("owner_id"));
        if (Boolean.TRUE.equals(rows.getFirst().get("is_guest"))
            && req.getRequestURI()
                .matches(
                    "/api/v1/(connectors|actions|signals|matrix|push|notification-preferences|browser).*")) {
          res.setStatus(403);
          res.setContentType("application/json");
          res.getWriter().write("{\"code\":\"SIGN_IN_REQUIRED\"}");
          return;
        }

        if (Boolean.TRUE.equals(rows.getFirst().get("is_guest"))
            && !Set.of("GET", "HEAD").contains(req.getMethod())
            && !req.getRequestURI()
                .matches(
                    "/api/v1/(auth/logout|conversations|conversations/[0-9a-f-]+(/messages|/stop)?)")) {
          res.setStatus(403);
          res.setContentType("application/json");
          res.getWriter().write("{\"code\":\"SIGN_IN_REQUIRED\"}");
          return;
        }
      } catch (Kernel.Problem e) {
        res.setStatus(403);
        res.setContentType("application/json");
        res.getWriter().write("{\"code\":\"ORIGIN_DENIED\"}");
        return;
      } catch (org.springframework.dao.DataAccessException e) {
        res.setStatus(503);
        res.setContentType("application/json");
        res.getWriter().write("{\"code\":\"DATABASE_UNAVAILABLE\"}");
        return;
      }
    }
    chain.doFilter(req, res);
  }
}
