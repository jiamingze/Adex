package io.adex.app.workspace;

import java.io.IOException;
import java.io.InputStream;

/** Streaming upload port: applications do not depend on servlet/multipart request objects. */
public interface UploadedFile {
  long getSize();

  boolean isEmpty();

  String getOriginalFilename();

  InputStream getInputStream() throws IOException;
}
