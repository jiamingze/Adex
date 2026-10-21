package io.adex.app.config;

import io.adex.app.conversation.ConversationStore;
import io.adex.app.identity.Auth;
import io.adex.app.memory.MemoryService;
import io.adex.app.notification.ApnsTransport;
import io.adex.kernel.Kernel;
import java.util.*;
import java.util.concurrent.*;
import org.springframework.web.bind.annotation.*;

/** HTTP adapter for Platform operations. */
@RestController
public class PlatformController {
  private final Kernel k;
  private final Auth auth;
  private final ConversationStore chat;
  private final MemoryService memory;

  public PlatformController(Kernel k, Auth auth, ConversationStore chat, MemoryService memory) {
    this.k = k;
    this.auth = auth;
    this.chat = chat;
    this.memory = memory;
  }

  @GetMapping("/api/v1/capabilities")
  public Object capabilities() {
    return Map.of(
        "chat_provider",
        Kernel.env("ADEX_MODEL_PROVIDER", "minimax"),
        "chat_model",
        Kernel.env("ADEX_MODEL_PROVIDER", "minimax").equals("qwen")
            ? Kernel.env("DASHSCOPE_CHAT_MODEL", "qwen3.8-flash")
            : Kernel.env("MINIMAX_MODEL", "MiniMax-M2.5"),
        "music_provider",
        Kernel.env("ADEX_MUSIC_PROVIDER", "mock"),
        "music_model",
        Kernel.env("DASHSCOPE_MUSIC_MODEL", ""),
        "music_max_seconds",
        600,
        "video_provider",
        Kernel.env("ADEX_VIDEO_PROVIDER", "mock"),
        "search_provider",
        "tavily",
        "offline_notifications",
        ApnsTransport.configured()
            ? "APNS_CONFIGURED_UNVERIFIED"
            : Kernel.env("ADEX_SMTP_HOST", "").isBlank() ? "BLOCKED_EXTERNAL" : "SMTP",
        "other_features",
        "TASK_MATRIX_PROACTIVE_ACTIONS");
  }
}
