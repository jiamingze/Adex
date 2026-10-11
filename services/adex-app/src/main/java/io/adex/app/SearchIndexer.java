package io.adex.app;

import io.adex.kernel.Kernel;
import java.net.URI;
import java.net.http.*;
import java.time.Duration;
import java.util.*;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/** ES is a rebuildable, asynchronous projection. Public reads remain PG-authoritative. */
@Component
public class SearchIndexer {
  private final Kernel k;

  public SearchIndexer(Kernel k) {
    this.k = k;
  }

  @Scheduled(fixedDelay = 5000)
  public void index() {
    String url = Kernel.env("ADEX_ES_URL", "");
    if (url.isBlank()) return;
    try {
      for (int i = 0; i < 10; i++) {
        var job =
            k.tx.execute(
                s -> {
                  var rows =
                      k.db.queryForList(
                          "SELECT * FROM outbox WHERE kind LIKE 'memory.index:%' AND delivered_at"
                              + " IS NULL AND next_attempt_at<=now() AND (lease_until IS NULL OR"
                              + " lease_until<now()) ORDER BY next_attempt_at FOR UPDATE SKIP"
                              + " LOCKED LIMIT 1");
                  if (rows.isEmpty()) return null;
                  return k.row(
                      "UPDATE outbox SET claim_id=?,lease_until=now()+interval '30 seconds' WHERE"
                          + " id=? RETURNING *",
                      Kernel.id(),
                      rows.getFirst().get("id"));
                });
        if (job == null) break;
        try {
          var mem = k.row("SELECT * FROM memories WHERE id=?", job.get("resource_id"));
          var doc = new LinkedHashMap<String, Object>();
          doc.put("owner_id", mem.get("owner_id"));
          doc.put("deleted", mem.get("deleted_at") != null);
          doc.put("content", mem.get("deleted_at") == null ? mem.get("content") : "");
          doc.put("revision", mem.get("revision"));
          var builder =
              HttpRequest.newBuilder(
                      URI.create(
                          url
                              + "/adex-memories/_doc/"
                              + mem.get("id")
                              + "?version="
                              + mem.get("revision")
                              + "&version_type=external_gte"))
                  .timeout(Duration.ofSeconds(5))
                  .header("Content-Type", "application/json");
          String key = Kernel.env("ADEX_ES_API_KEY", "");
          if (!key.isBlank()) builder.header("Authorization", "ApiKey " + key);
          var response =
              k.http.send(
                  builder.PUT(HttpRequest.BodyPublishers.ofString(k.encode(doc))).build(),
                  HttpResponse.BodyHandlers.discarding());
          if (response.statusCode() >= 400 && response.statusCode() != 409)
            throw new IllegalStateException("Index unavailable");
          k.db.update(
              "UPDATE outbox SET delivered_at=now(),lease_until=NULL WHERE id=? AND claim_id=?",
              job.get("id"),
              job.get("claim_id"));
        } catch (Exception e) {
          k.db.update(
              "UPDATE outbox SET"
                  + " lease_until=NULL,attempt_count=attempt_count+1,next_attempt_at=now()+interval"
                  + " '30 seconds' WHERE id=? AND claim_id=?",
              job.get("id"),
              job.get("claim_id"));
        }
      }
    } catch (Exception ignored) {
    }
  }
}
