package io.adex.app.workspace;

import io.adex.kernel.Kernel;
import java.io.IOException;
import java.nio.file.Path;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;

/** Shared ownership and storage access; callers never depend on an HTTP controller. */
@Service
public class FileAccessService {
  private final FileUploadService uploads;
  private final Kernel k;
  private final LocalFileStorage storage;

  public FileAccessService(Kernel k, LocalFileStorage storage, FileUploadService uploads) {
    this.uploads = uploads;
    this.k = k;
    this.storage = storage;
  }

  public Path object(UUID id) throws IOException {
    return storage.path(id);
  }

  public Object upload(UUID owner, UploadedFile file, String key) throws Exception {
    return uploads.upload(owner, file, key);
  }

  public Path root() {
    return storage.root;
  }

  public Map<String, Object> owned(UUID id, UUID owner) {
    var rows =
        k.db.queryForList(
            "SELECT * FROM files WHERE id=? AND owner_id=? AND status='READY'", id, owner);
    if (rows.isEmpty()) throw Kernel.error(404, "FILE_NOT_FOUND");
    return rows.getFirst();
  }
}
