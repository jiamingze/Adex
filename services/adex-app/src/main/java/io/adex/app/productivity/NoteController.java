package io.adex.app.productivity;

import io.adex.app.identity.Auth;
import jakarta.servlet.http.HttpServletRequest;
import java.util.*;
import org.springframework.web.bind.annotation.*;

@RestController
public class NoteController {
  private final Auth auth;
  private final NoteService service;

  public NoteController(Auth auth, NoteService service) {
    this.auth = auth;
    this.service = service;
  }

  @GetMapping("/api/v1/notes")
  public Object list(HttpServletRequest r, @RequestParam(defaultValue = "") String query) {
    return service.list(auth.owner(r), query);
  }

  @GetMapping("/api/v1/notes/{id}")
  public Object get(HttpServletRequest r, @PathVariable UUID id) {
    return service.get(auth.owner(r), id);
  }

  @PostMapping("/api/v1/notes")
  public Object create(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    return service.save(auth.owner(r), null, b);
  }

  @PatchMapping("/api/v1/notes/{id}")
  public Object update(
      HttpServletRequest r, @PathVariable UUID id, @RequestBody Map<String, Object> b) {
    return service.save(auth.owner(r), id, b);
  }

  @DeleteMapping("/api/v1/notes/{id}")
  public Object delete(HttpServletRequest r, @PathVariable UUID id, @RequestParam long revision) {
    return service.delete(auth.owner(r), id, revision);
  }
}
