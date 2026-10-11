package io.adex.app.workspace;

import io.adex.app.identity.Auth;
import io.adex.kernel.Kernel;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@RestController
public class FileApi {
  final Kernel k;
  final Auth auth;
  final Path root;
  static final long MAX = 25 * 1024 * 1024, QUOTA = 250 * 1024 * 1024;
  final LocalFileStorage storage;
  final FileUploadService uploads;

  public FileApi(Kernel k, Auth auth, LocalFileStorage storage, FileUploadService uploads) {
    this.uploads = uploads;
    this.k = k;
    this.auth = auth;
    this.storage = storage;
    root = storage.root;
  }

  Path object(UUID id) throws IOException {
    return storage.path(id);
  }

  Map<String, Object> owned(UUID id, UUID owner) {
    var rows =
        k.db.queryForList(
            "SELECT * FROM files WHERE id=? AND owner_id=? AND status='READY'", id, owner);
    if (rows.isEmpty()) throw Kernel.error(404, "FILE_NOT_FOUND");
    return rows.getFirst();
  }

  @GetMapping("/internal/files/{id}")
  public Object internalMetadata(HttpServletRequest request, @PathVariable UUID id) {
    var claims = k.require(request, "tools", "file:read", id);
    return owned(id, Kernel.uuid(claims.get("owner")));
  }

  @GetMapping("/internal/files/{id}/content")
  public void internalRead(
      HttpServletRequest request, HttpServletResponse response, @PathVariable UUID id)
      throws Exception {
    var claims = k.require(request, "tools", "file:read", id);
    request.setAttribute("owner", Kernel.uuid(claims.get("owner")));
    content(request, response, id);
  }

  @PostMapping("/internal/files")
  public Object internal(
      HttpServletRequest request,
      @RequestPart("file") MultipartFile file,
      @RequestHeader("Idempotency-Key") String key)
      throws Exception {
    var claims = k.require(request, "tools", "file:write", null);
    request.setAttribute("owner", Kernel.uuid(claims.get("owner")));
    return upload(request, file, key);
  }

  @PostMapping("/api/v1/files")
  public Object upload(
      HttpServletRequest request,
      @RequestPart("file") MultipartFile file,
      @RequestHeader("Idempotency-Key") String key)
      throws Exception {
    return uploads.upload(auth.owner(request), new MultipartUpload(file), key);
  }

  @PostMapping("/api/v1/files/{id}/playback")
  public Object playback(HttpServletRequest r, @PathVariable UUID id) {
    UUID owner = auth.owner(r);
    var file = owned(id, owner);
    String mime = String.valueOf(file.get("mime_type"));
    if (!mime.startsWith("audio/") && !mime.startsWith("video/"))
      throw Kernel.error(400, "NOT_PLAYABLE_MEDIA");
    k.db.update("DELETE FROM playback_tickets WHERE expires_at<now()");
    String token = Kernel.id().toString() + Kernel.id();
    k.db.update(
        "INSERT INTO playback_tickets(token_hash,owner_id,file_id,session_hash,expires_at) VALUES(?,?,?,?,now()+interval '15 minutes')",
        Kernel.hash(token),
        owner,
        id,
        Kernel.hash(auth.sessionToken(r)));
    return Map.of(
        "url", "/api/v1/media/" + token, "expires_in", 900, "availability", "USER_LIBRARY");
  }

  @GetMapping("/api/v1/media/{ticket}")
  public void streamTicket(
      HttpServletRequest r, HttpServletResponse response, @PathVariable String ticket)
      throws Exception {
    if (ticket.length() > 100) throw Kernel.error(404, "MEDIA_TICKET_NOT_FOUND");
    var rows =
        k.db.queryForList(
            "SELECT p.* FROM playback_tickets p JOIN sessions s ON s.token_hash=p.session_hash WHERE p.token_hash=? AND p.expires_at>clock_timestamp() AND s.expires_at>clock_timestamp()",
            Kernel.hash(ticket));
    if (rows.isEmpty()) throw Kernel.error(401, "MEDIA_TICKET_EXPIRED");
    var row = rows.getFirst();
    r.setAttribute("owner", row.get("owner_id"));
    response.setHeader("Referrer-Policy", "no-referrer");
    content(r, response, (UUID) row.get("file_id"));
  }

  @GetMapping("/api/v1/files")
  public Object list(HttpServletRequest r) {
    return Kernel.items(
        k.db.queryForList(
            "SELECT id,name,mime_type,size_bytes,sha256,status,created_at FROM files WHERE owner_id=? AND status='READY' ORDER BY created_at DESC LIMIT 200",
            auth.owner(r)));
  }

  @GetMapping("/api/v1/files/{id}")
  public Object metadata(HttpServletRequest r, @PathVariable UUID id) {
    return owned(id, auth.owner(r));
  }

  @DeleteMapping("/api/v1/files/{id}")
  public Object delete(HttpServletRequest r, @PathVariable UUID id) {
    return k.tx.execute(
        s -> {
          owned(id, auth.owner(r));
          k.db.queryForObject("SELECT id FROM files WHERE id=? FOR UPDATE", UUID.class, id);
          if (k.db.queryForObject(
                  "SELECT count(*) FROM artifact_versions v JOIN artifacts a ON a.id=v.artifact_id WHERE a.owner_id=? AND a.deleted_at IS NULL AND (v.file_id=? OR v.source->'media'->>'poster_file_id'=? OR v.source->'media'->'input_refs' @> ?::jsonb)",
                  Long.class,
                  auth.owner(r),
                  id,
                  id.toString(),
                  k.encode(List.of(id)))
              > 0) throw Kernel.error(409, "FILE_REFERENCED");
          if (k.db.queryForObject(
                  "SELECT count(*) FROM artifact_exports e JOIN artifacts a ON a.id=e.artifact_id WHERE e.file_id=? AND a.deleted_at IS NULL",
                  Long.class,
                  id)
              > 0) throw Kernel.error(409, "FILE_REFERENCED");
          k.db.update("UPDATE files SET status='DELETED',deleted_at=now() WHERE id=?", id);
          return Map.of("ok", true);
        });
  }

  @GetMapping("/api/v1/files/{id}/content")
  public void content(HttpServletRequest r, HttpServletResponse response, @PathVariable UUID id)
      throws Exception {
    var row = owned(id, auth.owner(r));
    Path path = object((UUID) row.get("object_id"));
    long length = ((Number) row.get("size_bytes")).longValue();
    if (!Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS) || Files.size(path) != length)
      throw Kernel.error(503, "FILE_INTEGRITY_ERROR");
    var hash = MessageDigest.getInstance("SHA-256");
    try (var input = Files.newInputStream(path)) {
      byte[] bytes = new byte[65536];
      int n;
      while ((n = input.read(bytes)) != -1) hash.update(bytes, 0, n);
    }
    if (!HexFormat.of().formatHex(hash.digest()).equals(row.get("sha256")))
      throw Kernel.error(503, "FILE_INTEGRITY_ERROR");
    long start = 0, end = length - 1;
    String range = r.getHeader("Range");
    if (range != null) {
      try {
        if (!range.matches("bytes=\\d*-\\d*")) throw new Exception();
        String[] bounds = range.substring(6).split("-", -1);
        if (bounds[0].isEmpty()) {
          long suffix = Long.parseLong(bounds[1]);
          if (suffix <= 0) throw new Exception();
          start = Math.max(0, length - suffix);
        } else {
          start = Long.parseLong(bounds[0]);
          if (!bounds[1].isEmpty()) end = Math.min(end, Long.parseLong(bounds[1]));
        }
        if (start < 0 || start >= length || end < start) throw new Exception();
        response.setStatus(206);
        response.setHeader("Content-Range", "bytes " + start + "-" + end + "/" + length);
      } catch (Exception e) {
        response.setStatus(416);
        response.setHeader("Content-Range", "bytes */" + length);
        return;
      }
    }
    response.setHeader("Accept-Ranges", "bytes");
    response.setHeader("Cache-Control", "private, no-store");
    response.setHeader("X-Content-Type-Options", "nosniff");
    response.setHeader("Content-Disposition", "attachment; filename=\"download\"");
    response.setHeader("ETag", "\"" + row.get("sha256") + "\"");
    response.setContentType((String) row.get("mime_type"));
    response.setContentLengthLong(end - start + 1);
    try (RandomAccessFile in = new RandomAccessFile(path.toFile(), "r")) {
      in.seek(start);
      byte[] buffer = new byte[65536];
      long left = end - start + 1;
      while (left > 0) {
        int n = in.read(buffer, 0, (int) Math.min(buffer.length, left));
        if (n < 0) throw new IOException("Truncated object");
        response.getOutputStream().write(buffer, 0, n);
        left -= n;
      }
    }
  }
}
