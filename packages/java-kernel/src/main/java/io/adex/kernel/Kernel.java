package io.adex.kernel;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import java.net.URI;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.*;
import java.util.*;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

@Component
public class Kernel {
  public final JdbcTemplate db;
  public final TransactionTemplate tx;
  public final ObjectMapper json;
  public final HttpClient http =
      HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
  public final String service = env("ADEX_SERVICE");

  public Kernel(JdbcTemplate db, PlatformTransactionManager tm, ObjectMapper json) {
    this.db = db;
    this.tx = new TransactionTemplate(tm);
    this.json = json;
    var module=new com.fasterxml.jackson.databind.module.SimpleModule();
    module.addSerializer(org.postgresql.util.PGobject.class,new com.fasterxml.jackson.databind.JsonSerializer<org.postgresql.util.PGobject>() {
      @Override public void serialize(org.postgresql.util.PGobject value,com.fasterxml.jackson.core.JsonGenerator generator,com.fasterxml.jackson.databind.SerializerProvider provider) throws java.io.IOException {
        if("jsonb".equals(value.getType())||"json".equals(value.getType()))generator.writeTree(json.readTree(value.getValue()));
        else generator.writeString(value.getValue());
      }
    });
    json.registerModule(module);
    env("ADEX_" + service.toUpperCase() + "_KEY");
  }

  public static String env(String k) {
    String v = System.getenv(k);
    if (v == null || v.isBlank()) throw new IllegalStateException("Required configuration: " + k);
    return v;
  }

  public static String env(String k, String d) {
    return System.getenv().getOrDefault(k, d);
  }

  public static UUID id() {
    return UUID.randomUUID();
  }

  public static UUID uuid(Object o) {
    try {
      return UUID.fromString(String.valueOf(o));
    } catch (Exception e) {
      throw error(400, "INVALID_ID");
    }
  }

  public static String text(Map<String, Object> b, String k, int max) {
    Object v = b.get(k);
    if (!(v instanceof String s) || s.isBlank() || s.length() > max)
      throw error(400, "INVALID_" + k.toUpperCase());
    return s.strip();
  }

  public static long number(Map<String, Object> b, String k) {
    try {
      return ((Number) b.get(k)).longValue();
    } catch (Exception e) {
      throw error(400, "INVALID_" + k.toUpperCase());
    }
  }

  public static Problem error(int status, String code) {
    return new Problem(status, code);
  }

  public static class Problem extends RuntimeException {
    public final int status;
    public final String code;

    public Problem(int s, String c) {
      super(c);
      status = s;
      code = c;
    }
  }

  public String encode(Object o) {
    try {
      return json.writeValueAsString(o);
    } catch (Exception e) {
      throw new IllegalArgumentException("Invalid JSON");
    }
  }

  @SuppressWarnings("unchecked")
  public Map<String, Object> decode(String s) {
    try {
      return json.readValue(s, Map.class);
    } catch (Exception e) {
      throw error(400, "INVALID_JSON");
    }
  }

  public static String hash(String s) {
    try {
      return HexFormat.of()
          .formatHex(
              MessageDigest.getInstance("SHA-256").digest(s.getBytes(StandardCharsets.UTF_8)));
    } catch (Exception e) {
      throw new IllegalStateException(e);
    }
  }

  public static String memoryHash(String s) {
    return hash(s.strip().replaceAll("\\s+", " ").toLowerCase(Locale.ROOT));
  }

  private static byte[] sign(String key, String p) {
    try {
      Mac m = Mac.getInstance("HmacSHA256");
      m.init(new SecretKeySpec(key.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
      return m.doFinal(p.getBytes(StandardCharsets.UTF_8));
    } catch (Exception e) {
      throw new IllegalStateException(e);
    }
  }

  public String token(String aud, String scope, Object owner, Object resource) {
    String key = env("ADEX_" + service.toUpperCase() + "_KEY");
    if (key.length() < 32) throw new IllegalStateException("Service key too short");
    var p = new LinkedHashMap<String, Object>();
    p.put("iss", service);
    p.put("aud", aud);
    p.put("scope", scope);
    p.put("owner", owner == null ? "*" : owner.toString());
    p.put("resource", resource == null ? "*" : resource.toString());
    p.put("exp", Instant.now().getEpochSecond() + 180);
    p.put(
        "trace_id",
        org.slf4j.MDC.get("request_id") == null
            ? id().toString()
            : org.slf4j.MDC.get("request_id"));
    String payload =
        Base64.getUrlEncoder()
            .withoutPadding()
            .encodeToString(encode(p).getBytes(StandardCharsets.UTF_8));
    return payload
        + "."
        + Base64.getUrlEncoder().withoutPadding().encodeToString(sign(key, payload));
  }

  public Map<String, Object> claims(HttpServletRequest req) {
    try {
      String a = req.getHeader("Authorization");
      if (a == null || !a.startsWith("Bearer ")) throw error(401, "UNAUTHENTICATED");
      String[] t = a.substring(7).split("\\.");
      if (t.length != 2) throw error(401, "UNAUTHENTICATED");
      Map<String, Object> c =
          decode(new String(Base64.getUrlDecoder().decode(t[0]), StandardCharsets.UTF_8));
      String iss = String.valueOf(c.get("iss"));
      if (!Set.of("app", "agent", "automation", "tools").contains(iss))
        throw error(401, "UNAUTHENTICATED");
      if (!MessageDigest.isEqual(
              sign(env("ADEX_" + iss.toUpperCase() + "_KEY"), t[0]),
              Base64.getUrlDecoder().decode(t[1]))
          || !service.equals(c.get("aud"))
          || number(c, "exp") <= Instant.now().getEpochSecond()
          || number(c, "exp") > Instant.now().getEpochSecond() + 240)
        throw error(401, "UNAUTHENTICATED");
      return c;
    } catch (Problem e) {
      throw e;
    } catch (Exception e) {
      throw error(401, "UNAUTHENTICATED");
    }
  }

  public Map<String, Object> require(
      HttpServletRequest req, String issuer, String scope, Object resource) {
    Map<String, Object> c = claims(req);
    if (!issuer.equals(c.get("iss"))
        || !scope.equals(c.get("scope"))
        || (resource != null && !resource.toString().equals(c.get("resource"))))
      throw error(403, "SCOPE_DENIED");
    return c;
  }

  public Map<String, Object> call(
      String aud,
      String scope,
      Object owner,
      Object resource,
      String method,
      String path,
      Object body) {
    try {
      String base = env("ADEX_" + aud.toUpperCase() + "_URL");
      var b =
          HttpRequest.newBuilder(URI.create(base + path))
              .timeout(Duration.ofSeconds(scope.equals("schedule:draft") ? 150 : 15))
              .header("Authorization", "Bearer " + token(aud, scope, owner, resource))
              .header("Content-Type", "application/json");
      var response =
          http.send(
              b.method(
                      method,
                      body == null
                          ? HttpRequest.BodyPublishers.noBody()
                          : HttpRequest.BodyPublishers.ofString(encode(body)))
                  .build(),
              HttpResponse.BodyHandlers.ofString());
      if (response.statusCode() >= 400) {
        String code = "DEPENDENCY_UNAVAILABLE";
        try {
          code = String.valueOf(decode(response.body()).getOrDefault("code", code));
        } catch (Exception ignored) {
        }
        throw error(response.statusCode(), code);
      }
      return decode(response.body());
    } catch (Problem e) {
      throw e;
    } catch (Exception e) {
      throw error(503, "DEPENDENCY_UNAVAILABLE");
    }
  }

  public Map<String, Object> row(String sql, Object... a) {
    var r = db.queryForList(sql, a);
    if (r.isEmpty()) throw error(404, "NOT_FOUND");
    return r.getFirst();
  }

  public static Map<String, Object> items(List<?> a) {
    return Map.of("items", a);
  }
}
