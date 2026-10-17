package io.adex.app.notification;

import io.adex.app.security.SecretEnvelope;
import io.adex.kernel.Kernel;
import java.time.Instant;
import java.util.*;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

/** Durable notification delivery worker, not a second task or Run scheduler. */
@Service
public class PushService {
  private final Kernel k;
  private final ApnsTransport transport;

  public PushService(Kernel k, ApnsTransport transport) {
    this.k = k;
    this.transport = transport;
  }

  public Object register(UUID owner, Map<String, Object> b) {
    String device = Kernel.text(b, "token", 512).toLowerCase(),
        environment = Kernel.text(b, "environment", 20);
    if (!device.matches("[a-f0-9]{32,512}")
        || device.length() % 2 != 0
        || !Set.of("sandbox", "production").contains(environment))
      throw Kernel.error(400, "INVALID_PUSH_DEVICE");
    return k.tx.execute(
        tx -> {
          k.db.queryForObject(
              "SELECT pg_advisory_xact_lock(hashtextextended(?,0))",
              Object.class,
              "push:" + Kernel.hash(device));
          var existing =
              k.db.queryForList(
                  "SELECT id FROM push_devices WHERE token_hash=? FOR UPDATE", Kernel.hash(device));
          UUID id = existing.isEmpty() ? Kernel.id() : Kernel.uuid(existing.getFirst().get("id"));
          String cipher = SecretEnvelope.push().seal(device, owner + ":" + id);
          k.db.update(
              "INSERT INTO push_devices(id,owner_id,token_hash,token_cipher,environment) VALUES(?,?,?,?,?) ON CONFLICT(token_hash) DO UPDATE SET owner_id=excluded.owner_id,token_cipher=excluded.token_cipher,environment=excluded.environment,created_at=CASE WHEN push_devices.owner_id<>excluded.owner_id OR NOT push_devices.active THEN clock_timestamp() ELSE push_devices.created_at END,active=true",
              id,
              owner,
              Kernel.hash(device),
              cipher,
              environment);
          return Map.of(
              "id",
              id,
              "availability",
              ApnsTransport.configured() ? "CONFIGURED_UNVERIFIED" : "BLOCKED_EXTERNAL");
        });
  }

  public Object revoke(UUID owner, UUID id) {
    if (k.db.update("UPDATE push_devices SET active=false WHERE id=? AND owner_id=?", id, owner)
        != 1) throw Kernel.error(404, "NOT_FOUND");
    return Map.of("ok", true);
  }

  public Object status(UUID owner) {
    return Map.of(
        "availability",
        ApnsTransport.configured() ? "CONFIGURED_UNVERIFIED" : "BLOCKED_EXTERNAL",
        "devices",
        k.db.queryForObject(
            "SELECT count(*) FROM push_devices WHERE owner_id=? AND active", Long.class, owner),
        "deliveries",
        k.db.queryForList(
            "SELECT p.status,p.error_code,p.completed_at FROM push_deliveries p JOIN notifications n ON n.id=p.notification_id WHERE n.owner_id=? ORDER BY n.created_at DESC LIMIT 5",
            owner));
  }

  public Object test(UUID owner, Map<String, Object> body) {
    UUID event = Kernel.uuid(body.get("event_id")), conv = Kernel.uuid(body.get("conversation_id"));
    if (event == null || conv == null) throw Kernel.error(400, "INVALID_PUSH_TEST");
    return k.tx.execute(
        tx -> {
          k.row(
              "SELECT id FROM conversations WHERE id=? AND owner_id=? AND deleted_at IS NULL",
              conv,
              owner);
          k.db.queryForObject(
              "SELECT pg_advisory_xact_lock(hashtextextended(?,0))",
              Object.class,
              "push-test:" + owner);
          var existing =
              k.db.queryForList(
                  "SELECT id FROM notifications WHERE event_id=? AND owner_id=?", event, owner);
          if (!existing.isEmpty()) return Map.of("notification_id", existing.getFirst().get("id"));
          if (k.db.queryForObject(
                  "SELECT count(*) FROM notifications WHERE owner_id=? AND title='Adex 推送测试' AND created_at>now()-interval '30 seconds'",
                  Long.class,
                  owner)
              > 0) throw Kernel.error(429, "PUSH_TEST_RATE_LIMITED");
          UUID id = Kernel.id();
          k.db.update(
              "INSERT INTO notifications(id,event_id,owner_id,conversation_id,title,body,importance) VALUES(?,?,?,?,?,?,100)",
              id,
              event,
              owner,
              conv,
              "Adex 推送测试",
              "测试通知，点击后回到关联会话。");
          return Map.of("notification_id", id);
        });
  }

  @Scheduled(fixedDelay = 3000)
  public void deliver() {
    try {
      // Ambiguous/crashed dispatch cannot be labelled delivered or blindly resent.
      k.db.update(
          "UPDATE push_deliveries SET status='UNKNOWN',error_code='DISPATCH_INTERRUPTED' WHERE status='IN_FLIGHT' AND dispatched_at<now()-interval '2 minutes'");
      k.db.update(
          "INSERT INTO push_deliveries(notification_id,device_id,status,apns_id) SELECT n.id,d.id,?,gen_random_uuid() FROM notifications n JOIN push_devices d ON d.owner_id=n.owner_id AND d.active JOIN notification_preferences p ON p.owner_id=n.owner_id WHERE p.enabled AND p.push_enabled AND n.importance>=p.min_importance AND NOT n.read AND n.created_at>now()-interval '1 day' AND n.created_at>=d.created_at AND (n.matrix_reminder_id IS NULL OR EXISTS (SELECT 1 FROM matrix_reminders mr JOIN matrix_tasks mt ON mt.id=mr.task_id AND mt.owner_id=mr.owner_id WHERE mr.id=n.matrix_reminder_id AND mr.owner_id=n.owner_id AND mt.important AND mt.status='TODO' AND mt.due_at=mr.due_at AND mt.due_at>clock_timestamp())) ON CONFLICT DO NOTHING",
          ApnsTransport.configured() ? "PREPARED" : "BLOCKED_EXTERNAL");
      if (!ApnsTransport.configured()) return;
      k.db.update("UPDATE push_deliveries SET status='PREPARED' WHERE status='BLOCKED_EXTERNAL'");
      var item =
          k.tx.execute(
              tx -> {
                var rows =
                    k.db.queryForList(
                        "SELECT x.notification_id,x.device_id,x.apns_id,n.id,n.conversation_id,n.run_id,n.action_id,d.owner_id,d.token_cipher,d.environment,p.quiet_start,p.quiet_end,p.timezone FROM push_deliveries x JOIN notifications n ON n.id=x.notification_id JOIN push_devices d ON d.id=x.device_id AND d.owner_id=n.owner_id JOIN notification_preferences p ON p.owner_id=n.owner_id WHERE x.status='PREPARED' AND d.active AND p.enabled AND p.push_enabled AND NOT n.read AND n.importance>=p.min_importance AND n.created_at>now()-interval '1 day' AND (p.quiet_start IS NULL OR CASE WHEN p.quiet_start<p.quiet_end THEN ((clock_timestamp() AT TIME ZONE p.timezone)::time<p.quiet_start OR (clock_timestamp() AT TIME ZONE p.timezone)::time>=p.quiet_end) ELSE ((clock_timestamp() AT TIME ZONE p.timezone)::time<p.quiet_start AND (clock_timestamp() AT TIME ZONE p.timezone)::time>=p.quiet_end) END) AND (n.matrix_reminder_id IS NULL OR EXISTS (SELECT 1 FROM matrix_reminders mr JOIN matrix_tasks mt ON mt.id=mr.task_id AND mt.owner_id=mr.owner_id WHERE mr.id=n.matrix_reminder_id AND mr.owner_id=n.owner_id AND mt.important AND mt.status='TODO' AND mt.due_at=mr.due_at AND mt.due_at>clock_timestamp())) ORDER BY n.created_at FOR UPDATE OF x SKIP LOCKED LIMIT 20");
                for (var row : rows) {
                  if (NotificationPreferences.quiet(
                      row.get("quiet_start") == null ? null : row.get("quiet_start").toString(),
                      row.get("quiet_end") == null ? null : row.get("quiet_end").toString(),
                      row.get("timezone").toString(),
                      Instant.now())) continue;
                  k.db.update(
                      "UPDATE push_deliveries SET status='IN_FLIGHT',dispatched_at=now() WHERE notification_id=? AND device_id=?",
                      row.get("notification_id"),
                      row.get("device_id"));
                  return row;
                }
                return null;
              });
      if (item == null) return;
      String status = "UNKNOWN", error = null;
      try {
        String device =
            SecretEnvelope.push()
                .open(
                    item.get("token_cipher").toString(),
                    item.get("owner_id") + ":" + item.get("device_id"));
        int code =
            transport.send(
                device,
                item.get("environment").toString(),
                Kernel.uuid(item.get("apns_id")),
                ApnsTransport.payload(item));
        status = code == 200 ? "ACCEPTED" : code >= 500 || code == 429 ? "UNKNOWN" : "FAILED";
        error = code == 200 ? null : "APNS_HTTP_" + code;
        if (code == 410)
          k.db.update("UPDATE push_devices SET active=false WHERE id=?", item.get("device_id"));
      } catch (Exception e) {
        error = "APNS_RESULT_UNKNOWN";
      }
      k.db.update(
          "UPDATE push_deliveries SET status=?,error_code=?,completed_at=now() WHERE notification_id=? AND device_id=? AND status='IN_FLIGHT'",
          status,
          error,
          item.get("notification_id"),
          item.get("device_id"));
    } catch (org.springframework.dao.DataAccessException e) {
      /* PG outage: leave durable state untouched; next delivery pass retries preparation. */
    }
  }
}
