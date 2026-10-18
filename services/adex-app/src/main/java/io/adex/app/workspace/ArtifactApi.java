package io.adex.app.workspace;

import io.adex.app.identity.Auth;
import io.adex.kernel.Kernel;
import jakarta.servlet.http.HttpServletRequest;
import java.util.*;
import org.springframework.web.bind.annotation.*;

@RestController
public class ArtifactApi {
  final Kernel k;
  final Auth auth;
  final FileAccessService files;

  public ArtifactApi(Kernel k, Auth auth, FileAccessService files) {
    this.k = k;
    this.auth = auth;
    this.files = files;
  }

  Map<String, Object> owned(UUID id, UUID owner) {
    var rows =
        k.db.queryForList(
            "SELECT * FROM artifacts WHERE id=? AND owner_id=? AND deleted_at IS NULL", id, owner);
    if (rows.isEmpty()) throw Kernel.error(404, "ARTIFACT_NOT_FOUND");
    return rows.getFirst();
  }

  @GetMapping("/api/v1/artifacts")
  public Object list(HttpServletRequest r) {
    return Kernel.items(
        k.db.queryForList(
            "SELECT * FROM artifacts WHERE owner_id=? AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 200",
            auth.owner(r)));
  }

  @PostMapping("/api/v1/artifacts")
  public Object create(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    String kind = Kernel.text(b, "kind", 40);
    if (!Set.of("REPORT", "TRAVEL", "DIAGRAM", "GAME", "IMAGE", "AUDIO", "VIDEO").contains(kind))
      throw Kernel.error(400, "INVALID_KIND");
    return k.row(
        "INSERT INTO artifacts(id,owner_id,kind,title) VALUES(?,?,?,?) RETURNING *",
        Kernel.id(),
        auth.owner(r),
        kind,
        Kernel.text(b, "title", 200));
  }

  @GetMapping("/api/v1/artifacts/{id}/versions")
  public Object versions(HttpServletRequest r, @PathVariable UUID id) {
    owned(id, auth.owner(r));
    return Kernel.items(
        k.db.queryForList(
            "SELECT * FROM artifact_versions WHERE artifact_id=? ORDER BY revision DESC", id));
  }

  @PostMapping("/api/v1/artifacts/{id}/versions")
  public Object save(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> b) {
    UUID owner = auth.owner(r);
    long expected = Kernel.number(b, "expected_revision");
    Object source = b.get("source");
    if (!(source instanceof Map)) throw Kernel.error(400, "INVALID_SOURCE");
    String serialized = k.encode(source);
    if (serialized.length() > 120000) throw Kernel.error(413, "SOURCE_TOO_LARGE");
    var artifact = owned(id, owner);
    if (((Number) artifact.get("revision")).longValue() != expected)
      throw Kernel.error(409, "REVISION_CONFLICT");
    UUID supplied = b.get("file_id") == null ? null : Kernel.uuid(b.get("file_id"));
    String kind = String.valueOf(artifact.get("kind"));
    if (supplied == null && Set.of("REPORT", "TRAVEL", "GAME", "DIAGRAM").contains(kind)) {
      Object content = ((Map<?, ?>) source).get("content");
      if (!(content instanceof String text) || text.isBlank())
        throw Kernel.error(400, "SOURCE_CONTENT_REQUIRED");
      String raw = text;
      if (kind.equals("GAME") || kind.equals("DIAGRAM")) {
        raw = ArtifactSource.fenced(text);
      }
      if (kind.equals("DIAGRAM")
          && (raw.length() > 20000
              || ArtifactSource.hasUnsafeAngles(raw)
              || java.util.regex.Pattern.compile(
                      "%%\\{|javascript:|https?://|\\bclick\\b|\\bstyle\\b|\\bclassDef\\b",
                      java.util.regex.Pattern.CASE_INSENSITIVE)
                  .matcher(raw)
                  .find()
              || !raw.matches("(?s)\\s*(flowchart|graph|sequenceDiagram|classDiagram)\\b.*")))
        throw Kernel.error(400, "UNSAFE_DIAGRAM");
      String name =
          kind.equals("GAME")
              ? "game.html"
              : kind.equals("DIAGRAM") ? "diagram.mmd" : "artifact.md";
      byte[] bytes = raw.getBytes(java.nio.charset.StandardCharsets.UTF_8);
      var upload =
          new org.springframework.web.multipart.MultipartFile() {
            public String getName() {
              return "file";
            }

            public String getOriginalFilename() {
              return name;
            }

            public String getContentType() {
              return "text/plain";
            }

            public boolean isEmpty() {
              return bytes.length == 0;
            }

            public long getSize() {
              return bytes.length;
            }

            public byte[] getBytes() {
              return bytes;
            }

            public java.io.InputStream getInputStream() {
              return new java.io.ByteArrayInputStream(bytes);
            }

            public void transferTo(java.io.File dest) throws java.io.IOException {
              java.nio.file.Files.write(dest.toPath(), bytes);
            }
          };
      try {
        var metadata =
            (Map<?, ?>)
                files.upload(
                    auth.owner(r),
                    new MultipartUpload(upload),
                    "revision:"
                        + id
                        + ":"
                        + expected
                        + ":"
                        + Kernel.hash(serialized).substring(0, 16));
        supplied = (UUID) metadata.get("id");
      } catch (java.io.IOException e) {
        throw Kernel.error(503, "ARTIFACT_FILE_WRITE_FAILED");
      } catch (Exception e) {
        if (e instanceof RuntimeException re) throw re;
        throw Kernel.error(503, "ARTIFACT_FILE_WRITE_FAILED");
      }
    }
    final UUID file = supplied;
    return k.tx.execute(
        s -> {
          owned(id, owner);
          var row = k.row("SELECT * FROM artifacts WHERE id=? FOR UPDATE", id);
          if (((Number) row.get("revision")).longValue() != expected)
            throw Kernel.error(409, "REVISION_CONFLICT");
          if (file != null) {
            var files =
                k.db.queryForList(
                    "SELECT id FROM files WHERE id=? AND owner_id=? AND status='READY' FOR SHARE",
                    file,
                    owner);
            if (files.isEmpty()) throw Kernel.error(404, "FILE_NOT_FOUND");
          }
          UUID parent =
              expected == 0
                  ? null
                  : k.db.queryForObject(
                      "SELECT id FROM artifact_versions WHERE artifact_id=? AND revision=?",
                      UUID.class,
                      id,
                      expected);
          var version =
              k.row(
                  "INSERT INTO artifact_versions(id,artifact_id,revision,source,file_id,sha256,parent_version_id) VALUES(?,?,?,?::jsonb,?,?,?) RETURNING *",
                  Kernel.id(),
                  id,
                  expected + 1,
                  serialized,
                  file,
                  Kernel.hash(serialized),
                  parent);
          k.db.update("UPDATE artifacts SET revision=revision+1 WHERE id=?", id);
          return version;
        });
  }

  @DeleteMapping("/api/v1/artifacts/{id}")
  public Object delete(HttpServletRequest r, @PathVariable UUID id) {
    UUID owner = auth.owner(r);
    return k.tx.execute(
        tx -> {
          owned(id, owner);
          k.db.update("UPDATE artifacts SET deleted_at=now() WHERE id=?", id);
          k.db.update("UPDATE artifact_shares SET revoked_at=now() WHERE artifact_id=?", id);
          return Map.of("ok", true);
        });
  }

  @PostMapping("/api/v1/artifacts/{id}/share")
  public Object share(HttpServletRequest r, @PathVariable UUID id) {
    return previewTicket(r, id, 86400);
  }

  @PostMapping("/api/v1/artifacts/{id}/preview")
  public Object previewTicket(HttpServletRequest r, @PathVariable UUID id) {
    return previewTicket(r, id, 300);
  }

  Object previewTicket(HttpServletRequest r, UUID id, int seconds) {
    UUID owner = auth.owner(r);
    var artifact = owned(id, owner);
    if (!artifact.get("kind").equals("GAME"))
      throw Kernel.error(400, "ONLY_GAME_PREVIEW_SHARE_SUPPORTED");
    UUID version =
        k.db.queryForObject(
            "SELECT id FROM artifact_versions WHERE artifact_id=? ORDER BY revision DESC LIMIT 1",
            UUID.class,
            id);
    String token = Kernel.id().toString() + Kernel.id();
    k.db.update(
        "INSERT INTO artifact_shares(token_hash,owner_id,artifact_id,version_id,expires_at) VALUES(?,?,?,?,now()+make_interval(secs=>?))",
        Kernel.hash(token),
        owner,
        id,
        version,
        seconds);
    return Map.of("url", "/api/v1/previews/" + token, "expires_in", seconds);
  }

  @DeleteMapping("/api/v1/artifacts/{id}/share")
  public Object revokeShares(HttpServletRequest r, @PathVariable UUID id) {
    owned(id, auth.owner(r));
    k.db.update("UPDATE artifact_shares SET revoked_at=now() WHERE artifact_id=?", id);
    return Map.of("ok", true);
  }

  @GetMapping("/api/v1/previews/{token}")
  public void preview(jakarta.servlet.http.HttpServletResponse response, @PathVariable String token)
      throws java.io.IOException {
    if (token.length() > 100) throw Kernel.error(404, "PREVIEW_NOT_FOUND");
    var rows =
        k.db.queryForList(
            "SELECT v.source FROM artifact_shares s JOIN artifacts a ON a.id=s.artifact_id JOIN artifact_versions v ON v.id=s.version_id WHERE s.token_hash=? AND s.revoked_at IS NULL AND s.expires_at>clock_timestamp() AND a.deleted_at IS NULL",
            Kernel.hash(token));
    if (rows.isEmpty()) throw Kernel.error(404, "PREVIEW_NOT_FOUND");
    var source = k.decode(String.valueOf(rows.getFirst().get("source")));
    String html = String.valueOf(source.getOrDefault("content", ""));
    var match =
        java.util.regex.Pattern.compile(
                "```html\\s*\\n([\\s\\S]*?)```", java.util.regex.Pattern.CASE_INSENSITIVE)
            .matcher(html);
    if (match.find()) html = match.group(1);
    response.setHeader(
        "Content-Security-Policy",
        "sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; media-src data: blob:; connect-src 'none'; form-action 'none'; base-uri 'none'; frame-ancestors 'self'");
    response.setHeader("Referrer-Policy", "no-referrer");
    response.setContentType("text/html;charset=UTF-8");
    response.getWriter().write(html);
  }

  @PostMapping("/api/v1/artifacts/{id}/exports")
  public Object export(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> b) {
    UUID owner = auth.owner(r),
        version = Kernel.uuid(b.get("version_id")),
        file = Kernel.uuid(b.get("file_id"));
    String format = Kernel.text(b, "format", 10);
    if (!Set.of("SVG", "PNG").contains(format)) throw Kernel.error(400, "INVALID_EXPORT_FORMAT");
    return k.tx.execute(
        tx -> {
          var artifact = owned(id, owner);
          if (!artifact.get("kind").equals("DIAGRAM"))
            throw Kernel.error(400, "INVALID_EXPORT_KIND");
          k.row(
              "SELECT id FROM artifact_versions WHERE id=? AND artifact_id=? FOR SHARE",
              version,
              id);
          var metadata = files.owned(file, owner);
          if (format.equals("PNG") && !metadata.get("mime_type").equals("image/png"))
            throw Kernel.error(400, "INVALID_EXPORT_FILE");
          if (format.equals("SVG")) {
            if (((Number) metadata.get("size_bytes")).longValue() > 2000000)
              throw Kernel.error(413, "EXPORT_FILE_TOO_LARGE");
            try {
              String svg =
                  java.nio.file.Files.readString(files.object((UUID) metadata.get("object_id")));
              if (svg.length() > 2000000
                  || !svg.contains("<svg")
                  || java.util.regex.Pattern.compile(
                          "(?is)<!|<script|<foreignObject|<iframe|<image|<animate|<set[\\s>]|<mpath|<a[\\s>]|\\son[a-z]+\\s*=|javascript:|(?:href|xlink:href)\\s*=")
                      .matcher(svg)
                      .find()) throw Kernel.error(400, "UNSAFE_EXPORT_FILE");
            } catch (java.io.IOException e) {
              throw Kernel.error(503, "EXPORT_READ_FAILED");
            }
          }
          k.db.update(
              "INSERT INTO artifact_exports(id,artifact_id,version_id,file_id,format,renderer_version) VALUES(?,?,?,?,?,'mermaid-12.1.0-svg-labels-v2') ON CONFLICT DO NOTHING",
              Kernel.id(),
              id,
              version,
              file,
              format);
          return Map.of("ok", true, "file_id", file);
        });
  }

  @GetMapping("/api/v1/artifacts/{id}/exports")
  public Object exports(HttpServletRequest r, @PathVariable UUID id) {
    owned(id, auth.owner(r));
    return Kernel.items(
        k.db.queryForList(
            "SELECT * FROM artifact_exports WHERE artifact_id=? ORDER BY created_at DESC", id));
  }
}
