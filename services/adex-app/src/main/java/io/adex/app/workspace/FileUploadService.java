package io.adex.app.workspace;

import io.adex.kernel.Kernel;
import java.io.*;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import org.springframework.stereotype.Service;

/**
 * Durable file import: fsync temporary bytes, reserve metadata, atomic rename, then READY. A crash
 * between these boundaries is reconciled by FileReconciler; pending bytes are never served.
 */
@Service
public class FileUploadService {
  private final Kernel k;
  private final LocalFileStorage storage;
  private final Path root;
  static final long MAX = 25 * 1024 * 1024, QUOTA = 250 * 1024 * 1024;

  public FileUploadService(Kernel k, LocalFileStorage storage) {
    this.k = k;
    this.storage = storage;
    this.root = storage.root;
  }

  private Path object(UUID id) throws IOException {
    return storage.path(id);
  }

  public Object upload(UUID owner, UploadedFile file, String key) throws Exception {

    if (key.isBlank() || key.length() > 128) throw Kernel.error(400, "INVALID_IDEMPOTENCY_KEY");
    if (file.getSize() > MAX || file.isEmpty()) throw Kernel.error(413, "FILE_SIZE_LIMIT");
    if (Files.getFileStore(root).getUsableSpace() < MAX + 64 * 1024 * 1024L)
      throw Kernel.error(507, "DISK_SPACE_LOW");
    UUID object = Kernel.id();
    Path target = object(object), temp = target.resolveSibling(object + ".tmp");
    MessageDigest digest = MessageDigest.getInstance("SHA-256");
    long size = 0;
    try {
      try (InputStream in = file.getInputStream();
          OutputStream out = Files.newOutputStream(temp, StandardOpenOption.CREATE_NEW)) {
        byte[] buffer = new byte[65536];
        int n;
        while ((n = in.read(buffer)) != -1) {
          size += n;
          if (size > MAX) throw Kernel.error(413, "FILE_SIZE_LIMIT");
          digest.update(buffer, 0, n);
          out.write(buffer, 0, n);
        }
      }
      try (FileChannel channel = FileChannel.open(temp, StandardOpenOption.WRITE)) {
        channel.force(true);
      }
      String hash = HexFormat.of().formatHex(digest.digest());
      final long bytes = size;
      String name =
          Optional.ofNullable(file.getOriginalFilename())
              .orElse("file")
              .replaceAll("[\\p{Cntrl}\\\\/]", "_");
      if (name.length() > 200) name = name.substring(0, 200);
      final String safeName = name;
      // Active MIME is never served inline; magic signatures determine playable formats.
      byte[] magic = new byte[16];
      try (InputStream in = Files.newInputStream(temp)) {
        in.read(magic);
      }
      String mime = "application/octet-stream";
      if (magic[0] == (byte) 0x89 && magic[1] == 'P' && magic[2] == 'N' && magic[3] == 'G')
        mime = "image/png";
      else if (magic[0] == (byte) 0xff && magic[1] == (byte) 0xd8) mime = "image/jpeg";
      else if (magic[0] == 'R' && magic[1] == 'I' && magic[2] == 'F' && magic[8] == 'W')
        mime = "audio/wav";
      else if (magic[0] == 'I' && magic[1] == 'D' && magic[2] == '3') mime = "audio/mpeg";
      else if (magic[0] == '%' && magic[1] == 'P' && magic[2] == 'D' && magic[3] == 'F')
        mime = "application/pdf";
      else if (magic[4] == 'f' && magic[5] == 't' && magic[6] == 'y' && magic[7] == 'p')
        mime = "video/mp4";
      final String type = mime;
      Map<String, Object> row =
          k.tx.execute(
              status -> {
                k.db.queryForObject(
                    "SELECT id FROM users WHERE id=? FOR UPDATE", UUID.class, owner);
                var old =
                    k.db.queryForList(
                        "SELECT * FROM files WHERE owner_id=? AND idempotency_key=?", owner, key);
                if (!old.isEmpty()) {
                  if (!hash.equals(old.getFirst().get("sha256")))
                    throw Kernel.error(409, "IDEMPOTENCY_CONFLICT");
                  return old.getFirst();
                }
                long used =
                    k.db.queryForObject(
                        "SELECT COALESCE(sum(size_bytes),0) FROM files WHERE owner_id=? AND status<>'DELETED'",
                        Long.class,
                        owner);
                if (used + bytes > QUOTA) throw Kernel.error(413, "FILE_QUOTA_LIMIT");
                return k.row(
                    "INSERT INTO files(id,owner_id,object_id,idempotency_key,name,mime_type,size_bytes,sha256,status) VALUES(?,?,?,?,?,?,?,?,'PENDING') RETURNING *",
                    Kernel.id(),
                    owner,
                    object,
                    key,
                    safeName,
                    type,
                    bytes,
                    hash);
              });
      if (!object.equals(row.get("object_id"))) return row;
      storage.put(object, temp);
      k.db.update("UPDATE files SET status='READY' WHERE id=? AND status='PENDING'", row.get("id"));
      return k.row(
          "SELECT * FROM files WHERE id=? AND owner_id=? AND status='READY'", row.get("id"), owner);
    } finally {
      Files.deleteIfExists(temp);
    }
  }
}
