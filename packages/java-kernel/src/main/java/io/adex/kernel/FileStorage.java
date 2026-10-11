package io.adex.kernel;

import java.io.*;
import java.nio.file.Path;
import java.util.UUID;

/** Only LocalFileStorage is implemented in Phase 1. IDs never contain user filenames. */
public interface FileStorage {
  record Metadata(long sizeBytes, boolean exists) {}

  void put(UUID objectId, Path temporary) throws IOException;

  InputStream read(UUID objectId) throws IOException;

  Metadata stat(UUID objectId) throws IOException;

  void delete(UUID objectId) throws IOException;
}
