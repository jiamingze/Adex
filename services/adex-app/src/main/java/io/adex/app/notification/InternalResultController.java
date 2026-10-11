package io.adex.app.notification;

import io.adex.kernel.Kernel;
import jakarta.servlet.http.HttpServletRequest;
import java.util.*;
import java.util.concurrent.*;
import org.springframework.web.bind.annotation.*;

/** HTTP adapter for InternalResult operations. */
@RestController
public class InternalResultController {
  private final Kernel k;
  private final ResultAttachmentService service;

  public InternalResultController(Kernel k, ResultAttachmentService service) {
    this.k = k;
    this.service = service;
  }

  @PostMapping("/internal/monitors/attach")
  public Object monitorAttach(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    return service.monitorAttach(
        k.require(r, "automation", "monitor:attach", Kernel.uuid(b.get("origin_conversation_id"))),
        b);
  }

  @PostMapping("/internal/results/attach")
  public Object attach(HttpServletRequest r, @RequestBody Map<String, Object> b) {
    return service.attach(
        k.require(r, "automation", "result:attach", Kernel.uuid(b.get("origin_conversation_id"))),
        b);
  }
}
