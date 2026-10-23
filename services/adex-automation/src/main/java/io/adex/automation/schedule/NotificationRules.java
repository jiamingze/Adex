package io.adex.automation.schedule;

import io.adex.kernel.Kernel;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.*;

/** Notification eligibility is independent of durable conversation result delivery. */
public final class NotificationRules {
  private NotificationRules() {}

  public static Map<String, Object> request(Map<String, Object> body) {
    var result = new LinkedHashMap<String, Object>();
    if (body.get("task_request") instanceof Map<?, ?> raw)
      raw.forEach((key, value) -> result.put(String.valueOf(key), value));
    String policy =
        String.valueOf(
            body.getOrDefault(
                "notification_policy", result.getOrDefault("notification_policy", "EVERY_RUN")));
    if (!Set.of("EVERY_RUN", "CHANGES_ONLY", "CONDITION_MET").contains(policy))
      throw Kernel.error(400, "INVALID_NOTIFICATION_POLICY");
    Object raw = body.getOrDefault("notification_condition", result.get("notification_condition"));
    if (policy.equals("CONDITION_MET")) {
      if (!(raw instanceof Map<?, ?> condition)
          || !condition.keySet().equals(Set.of("description", "operator", "threshold", "unit")))
        throw Kernel.error(400, "INVALID_NOTIFICATION_CONDITION");
      for (String key : List.of("description", "operator", "threshold", "unit"))
        if (!(condition.get(key) instanceof String))
          throw Kernel.error(400, "INVALID_NOTIFICATION_CONDITION");
      String description = (String) condition.get("description"),
          op = (String) condition.get("operator"),
          threshold = (String) condition.get("threshold"),
          unit = (String) condition.get("unit");
      if (description.isBlank()
          || description.length() > 1000
          || !Set.of("semantic", "lt", "lte", "gt", "gte", "eq").contains(op)
          || threshold.length() > 50
          || unit.length() > 40) throw Kernel.error(400, "INVALID_NOTIFICATION_CONDITION");
      if (op.equals("semantic")) {
        if (!threshold.isEmpty() || !unit.isEmpty())
          throw Kernel.error(400, "INVALID_NOTIFICATION_CONDITION");
      } else {
        try {
          new BigDecimal(threshold);
          if (unit.isBlank()) throw new IllegalArgumentException();
        } catch (IllegalArgumentException invalid) {
          throw Kernel.error(400, "INVALID_NOTIFICATION_CONDITION");
        }
      }
      result.put("notification_condition", new LinkedHashMap<>(condition));
    } else if (raw != null) throw Kernel.error(400, "INVALID_NOTIFICATION_CONDITION");
    result.put("notification_policy", policy);
    return result;
  }

  /** The application derives this from readback; the language model cannot set it. */
  public static String observationFingerprint(Map<String, Object> state) {
    if (state.get("artifact") instanceof Map<?, ?> artifact
        && artifact.get("observation_fingerprint") instanceof String value
        && value.matches("[a-f0-9]{64}")) return value;
    return null;
  }

  public static boolean observationChanged(
      String current, String content, Map<String, Object> previous) {
    Object prior = previous.get("observation_fingerprint");
    if (current != null && prior instanceof String value && value.matches("[a-f0-9]{64}"))
      return !current.equals(value);
    return !content.strip().equals(String.valueOf(previous.get("result")).strip());
  }

  public static boolean conditional(Map<String, Object> request) {
    return "CONDITION_MET".equals(request.get("notification_policy"));
  }

  public static boolean conditionMet(Map<String, Object> request, Map<String, Object> state) {
    try {
      if (!(request.get("notification_condition") instanceof Map<?, ?> condition)
          || !(state.get("notification_assessment") instanceof Map<?, ?> assessment)
          || !condition.equals(assessment.get("condition"))
          || !"MET".equals(assessment.get("status"))
          || !(assessment.get("evidence") instanceof List<?> evidence)
          || evidence.isEmpty()) return false;
      String op = String.valueOf(condition.get("operator"));
      String description = String.valueOf(condition.get("description"));
      boolean rendered =
          !op.equals("semantic")
              || List.of("价格", "金价", "黄金", "股价", "汇率").stream().anyMatch(description::contains);
      for (Object item : evidence) {
        if (!(item instanceof Map<?, ?> proof)
            || !String.valueOf(proof.get("url")).startsWith("https://")
            || !(proof.get("quote") instanceof String quote)
            || quote.isBlank()) return false;
        var observed = Instant.parse(String.valueOf(proof.get("fetched_at")));
        if (observed.isBefore(Instant.now().minusSeconds(3600))
            || observed.isAfter(Instant.now().plusSeconds(60))) return false;
        if (rendered && !"BROWSER_RENDERED_PAGE".equals(proof.get("source_kind"))) return false;
      }
      if (op.equals("semantic"))
        return true; // Explicit, evidence-backed model judgment; no external-action success claim.
      if (!condition.get("unit").equals(assessment.get("unit"))) return false;
      var value = new BigDecimal(String.valueOf(assessment.get("value")));
      var threshold = new BigDecimal(String.valueOf(condition.get("threshold")));
      int comparison = value.compareTo(threshold);
      return switch (op) {
        case "lt" -> comparison < 0;
        case "lte" -> comparison <= 0;
        case "gt" -> comparison > 0;
        case "gte" -> comparison >= 0;
        case "eq" -> comparison == 0;
        default -> false;
      };
    } catch (RuntimeException invalid) {
      return false;
    }
  }
}
