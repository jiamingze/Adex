package io.adex.automation;

import static org.junit.jupiter.api.Assertions.*;

import io.adex.automation.schedule.NotificationRules;
import java.time.Instant;
import java.util.*;
import org.junit.jupiter.api.Test;

class NotificationRulesTest {
  @Test
  void observationIdentityControlsChangesOnlyInsteadOfWording() {
    String same = "a".repeat(64), changed = "b".repeat(64);
    assertFalse(
        NotificationRules.observationChanged(
            same,
            "Rewritten summary",
            Map.of("observation_fingerprint", same, "result", "Original summary")));
    assertTrue(
        NotificationRules.observationChanged(
            changed,
            "Same wording",
            Map.of("observation_fingerprint", same, "result", "Same wording")));
    assertFalse(
        NotificationRules.observationChanged(null, " summary ", Map.of("result", "summary")));
    assertNull(
        NotificationRules.observationFingerprint(
            Map.of("artifact", Map.of("observation_fingerprint", "model says same"))));
  }

  @Test
  void numericEvidenceAndConditionControlNotificationNotAnswerText() {
    var condition =
        Map.of("description", "fixture", "operator", "lt", "threshold", "800", "unit", "CNY/g");
    var request =
        Map.<String, Object>of(
            "notification_policy", "CONDITION_MET", "notification_condition", condition);
    var proof =
        Map.of(
            "url",
            "https://example.test/price",
            "quote",
            "TEST_FIXTURE 790 元/克",
            "source_kind",
            "BROWSER_RENDERED_PAGE",
            "fetched_at",
            Instant.now().toString());
    var assessment =
        new HashMap<String, Object>(
            Map.of(
                "condition",
                condition,
                "status",
                "MET",
                "value",
                "790",
                "unit",
                "CNY/g",
                "evidence",
                List.of(proof)));
    assertTrue(
        NotificationRules.conditionMet(request, Map.of("notification_assessment", assessment)));
    assessment.put("value", "810");
    assertFalse(
        NotificationRules.conditionMet(request, Map.of("notification_assessment", assessment)));
    assessment.put("status", "UNKNOWN");
    assertFalse(
        NotificationRules.conditionMet(request, Map.of("notification_assessment", assessment)));
    assertFalse(NotificationRules.conditionMet(request, Map.of("content", "已满足条件")));
    assertThrows(
        RuntimeException.class,
        () -> NotificationRules.request(Map.of("notification_policy", "CONDITION_MET")));
  }
}
