package io.adex.app.memory;

import io.adex.kernel.Kernel;
import java.util.*;
import org.springframework.stereotype.Service;

/** Owns MemoryQuery use cases; HTTP authentication is performed by the adapter. */
@Service
public class MemoryQueryService {
  private final Kernel k;
  private final MemoryService memory;

  public MemoryQueryService(Kernel k, MemoryService memory) {
    this.k = k;
    this.memory = memory;
  }

  public Object memories(UUID owner) {
    return Kernel.items(
        k.db.queryForList(
            "SELECT id,content,source_refs,revision,created_at FROM memories WHERE owner_id=? AND"
                + " deleted_at IS NULL ORDER BY created_at DESC LIMIT 200",
            owner));
  }

  public Object memory(UUID owner, Map<String, Object> b) {
    return memory.save(owner, b);
  }

  public Object forget(UUID owner, UUID id) {
    memory.remove(owner, id);
    return Map.of("ok", true);
  }

  public Object correct(UUID owner, UUID id, Map<String, Object> b) {
    return memory.correct(owner, id, b);
  }
}
