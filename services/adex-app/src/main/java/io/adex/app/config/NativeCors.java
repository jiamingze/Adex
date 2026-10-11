package io.adex.app.config;

import io.adex.kernel.Kernel;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.*;

@Configuration
public class NativeCors implements WebMvcConfigurer {
  @Override
  public void addCorsMappings(CorsRegistry registry) {
    registry
        .addMapping("/api/v1/**")
        .allowedOrigins(Kernel.env("ADEX_ALLOWED_ORIGINS", "capacitor://localhost").split(","))
        .allowCredentials(true)
        .allowedMethods("GET", "POST", "PATCH", "DELETE", "OPTIONS")
        .allowedHeaders(
            "Authorization", "Content-Type", "Idempotency-Key", "Range", "Last-Event-ID")
        .exposedHeaders("Content-Range", "ETag")
        .maxAge(600);
  }
}
