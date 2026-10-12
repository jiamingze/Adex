package io.adex.app.notification;

import static org.junit.jupiter.api.Assertions.*;

import io.adex.app.security.SecretEnvelope;
import java.time.Instant;
import java.util.*;
import org.junit.jupiter.api.Test;

class NotificationSecurityTest {
  @Test
  void deviceCipherIsBoundToOwnerAndDevice() {
    var vault = new SecretEnvelope(new byte[32]);
    String cipher = vault.seal("fixture-device", "owner:device");
    assertNotEquals("fixture-device", cipher);
    assertEquals("fixture-device", vault.open(cipher, "owner:device"));
    assertThrows(RuntimeException.class, () -> vault.open(cipher, "other:device"));
  }

  @Test
  void quietHoursCrossMidnight() {
    assertTrue(
        NotificationPreferences.quiet(
            "22:00", "08:00", "Asia/Shanghai", Instant.parse("2026-10-12T16:00:00Z")));
    assertFalse(
        NotificationPreferences.quiet(
            "22:00", "08:00", "Asia/Shanghai", Instant.parse("2026-10-12T04:00:00Z")));
  }

  @Test
  void pushContainsOnlyGenericTextAndIdentifiers() {
    var id = UUID.randomUUID();
    var payload =
        ApnsTransport.payload(
            Map.of(
                "id",
                id,
                "conversation_id",
                UUID.randomUUID(),
                "run_id",
                UUID.randomUUID(),
                "action_id",
                UUID.randomUUID(),
                "body",
                "PRIVATE EMAIL CONTENT"));
    assertEquals(id.toString(), payload.get("notification_id"));
    assertFalse(payload.toString().contains("PRIVATE EMAIL"));
    assertTrue(payload.containsKey("action_id"));
  }
}
