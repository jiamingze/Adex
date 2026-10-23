package io.adex.app.speech;

import io.adex.app.identity.Auth;
import io.adex.kernel.Kernel;
import jakarta.servlet.http.HttpServletRequest;
import java.util.Map;
import java.util.UUID;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

/** An authenticated, owner-bound capability; never exposes a provider API key. */
@RestController
public class SpeechApi {
  private final Auth auth;
  private final Kernel kernel;

  public SpeechApi(Auth auth, Kernel kernel) {
    this.auth = auth;
    this.kernel = kernel;
  }

  @PostMapping("/api/v1/speech/session")
  public Object session(HttpServletRequest request) {
    var owner = auth.owner(request);
    var id = UUID.randomUUID();
    return Map.of("session_id", id, "token", kernel.token("tools", "speech:stream", owner, id));
  }
}
