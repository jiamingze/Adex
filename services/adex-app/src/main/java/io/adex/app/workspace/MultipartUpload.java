package io.adex.app.workspace;

import java.io.IOException;
import java.io.InputStream;
import org.springframework.web.multipart.MultipartFile;

/** HTTP multipart adapter for the streaming upload port. No bytes are buffered in memory. */
public record MultipartUpload(MultipartFile delegate) implements UploadedFile {
  public long getSize() {
    return delegate.getSize();
  }

  public boolean isEmpty() {
    return delegate.isEmpty();
  }

  public String getOriginalFilename() {
    return delegate.getOriginalFilename();
  }

  public InputStream getInputStream() throws IOException {
    return delegate.getInputStream();
  }
}
