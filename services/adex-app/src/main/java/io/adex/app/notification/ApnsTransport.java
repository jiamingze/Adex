package io.adex.app.notification;

import io.adex.kernel.Kernel;
import java.net.URI;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.*;
import java.security.spec.PKCS8EncodedKeySpec;
import java.time.*;
import java.util.*;
import org.springframework.stereotype.Component;

/** APNs HTTP/2 provider. ACCEPTED means Apple accepted, not device displayed/read. */
@Component
public class ApnsTransport {
  private final Kernel k;
  private String token;
  private long issuedAt;
  private final HttpClient client =
      HttpClient.newBuilder()
          .version(HttpClient.Version.HTTP_2)
          .connectTimeout(Duration.ofSeconds(10))
          .build();

  public ApnsTransport(Kernel k) {
    this.k = k;
  }

  public static boolean fixture() {
    return Kernel.env("ADEX_APNS_TEST_FIXTURE", "false").equals("true")
        && Kernel.env("ADEX_DB_JDBC_URL", "").contains("/adex_test_");
  }

  public static boolean configured() {
    return fixture()
        || (!Kernel.env("ADEX_APNS_KEY_FILE", "").isBlank()
            && !Kernel.env("ADEX_APNS_TEAM_ID", "").isBlank()
            && !Kernel.env("ADEX_APNS_KEY_ID", "").isBlank()
            && !Kernel.env("ADEX_APNS_TOPIC", "").isBlank());
  }

  public static Map<String, Object> payload(Map<String, Object> notification) {
    var payload = new LinkedHashMap<String, Object>();
    payload.put(
        "aps",
        Map.of(
            "alert", Map.of("title", "Adex", "body", "有一条任务结果或重要事项，请打开查看。"), "sound", "default"));
    for (String field : List.of("id", "conversation_id", "run_id", "action_id"))
      if (notification.get(field) != null)
        payload.put(
            field.equals("id") ? "notification_id" : field, notification.get(field).toString());
    return payload;
  }

  public int send(String device, String environment, UUID deliveryId, Map<String, Object> payload)
      throws Exception {
    if (!configured()) throw Kernel.error(503, "BLOCKED_EXTERNAL");
    String host =
        fixture()
            ? "http://127.0.0.1:18109/apns"
            : environment.equals("sandbox")
                ? "https://api.sandbox.push.apple.com"
                : "https://api.push.apple.com";
    var request =
        HttpRequest.newBuilder(URI.create(host + "/3/device/" + device))
            .timeout(Duration.ofSeconds(15))
            .header("authorization", "bearer " + (fixture() ? "TEST_FIXTURE" : jwt()))
            .header("apns-topic", Kernel.env("ADEX_APNS_TOPIC", "io.adex.personal"))
            .header("apns-push-type", "alert")
            .header("apns-id", deliveryId.toString())
            .header("apns-collapse-id", payload.get("notification_id").toString())
            .header(
                "apns-expiration",
                String.valueOf(Instant.now().plusSeconds(86400).getEpochSecond()))
            .POST(HttpRequest.BodyPublishers.ofString(k.encode(payload)))
            .build();
    return client.send(request, HttpResponse.BodyHandlers.discarding()).statusCode();
  }

  private synchronized String jwt() throws Exception {
    long now = Instant.now().getEpochSecond();
    if (token != null && now - issuedAt < 3000) return token;
    String header =
        base(
            k.encode(Map.of("alg", "ES256", "kid", Kernel.env("ADEX_APNS_KEY_ID")))
                .getBytes(StandardCharsets.UTF_8));
    String claims =
        base(
            k.encode(Map.of("iss", Kernel.env("ADEX_APNS_TEAM_ID"), "iat", now))
                .getBytes(StandardCharsets.UTF_8));
    String data = header + "." + claims;
    String pem =
        Files.readString(Path.of(Kernel.env("ADEX_APNS_KEY_FILE")))
            .replaceAll("-----[^-]+-----|\\s", "");
    var key =
        KeyFactory.getInstance("EC")
            .generatePrivate(new PKCS8EncodedKeySpec(Base64.getDecoder().decode(pem)));
    var signature = Signature.getInstance("SHA256withECDSAinP1363Format");
    signature.initSign(key);
    signature.update(data.getBytes(StandardCharsets.US_ASCII));
    token = data + "." + base(signature.sign());
    issuedAt = now;
    return token;
  }

  private static String base(byte[] value) {
    return Base64.getUrlEncoder().withoutPadding().encodeToString(value);
  }
}
