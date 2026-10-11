package io.adex.app.workspace;

import io.adex.kernel.*;
import java.io.*;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.*;
import org.springframework.stereotype.Component;

@Component
public class LocalFileStorage implements FileStorage {
  final Path root;

  public LocalFileStorage() throws IOException {
    root = Path.of(Kernel.env("ADEX_FILE_STORAGE_ROOT", ".local-data/files")).toAbsolutePath();
    if (Files.isSymbolicLink(root)) throw new IOException("Unsafe storage root");
    Files.createDirectories(root);
    Files.setPosixFilePermissions(root, PosixFilePermissions.fromString("rwx------"));
  }

  Path path(UUID object) throws IOException {
    Path shard = root.resolve(object.toString().substring(0, 2));
    if (Files.isSymbolicLink(shard)) throw new IOException("Unsafe shard");
    Files.createDirectories(shard);
    Files.setPosixFilePermissions(shard, PosixFilePermissions.fromString("rwx------"));
    Path p = shard.resolve(object.toString());
    if (Files.isSymbolicLink(p)) throw new IOException("Unsafe object");
    return p;
  }

  @Override
  public void put(UUID object, Path temporary) throws IOException {
    Path target = path(object);
    if (!temporary.equals(target.resolveSibling(object + ".tmp")))
      throw new IOException("Invalid temporary object");
    Files.move(temporary, target, StandardCopyOption.ATOMIC_MOVE);
    try (FileChannel directory = FileChannel.open(target.getParent(), StandardOpenOption.READ)) {
      directory.force(true);
    }
  }

  @Override
  public InputStream read(UUID object) throws IOException {
    return Files.newInputStream(path(object), LinkOption.NOFOLLOW_LINKS);
  }

  @Override
  public Metadata stat(UUID object) throws IOException {
    Path p = path(object);
    boolean exists = Files.isRegularFile(p, LinkOption.NOFOLLOW_LINKS);
    return new Metadata(exists ? Files.size(p) : 0, exists);
  }

  @Override
  public void delete(UUID object) throws IOException {
    Files.deleteIfExists(path(object));
  }
}
