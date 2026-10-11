package io.adex.kernel;

import jakarta.servlet.*;
import jakarta.servlet.http.*;
import java.io.IOException;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/** Logs metadata only: never request bodies, authorization headers or provider content. */
@Component
@Order(-100)
public class RequestTrace extends OncePerRequestFilter {
  private static final Logger log = LoggerFactory.getLogger(RequestTrace.class);

  @Override
  protected void doFilterInternal(
      HttpServletRequest req, HttpServletResponse res, FilterChain chain)
      throws ServletException, IOException {
    String trace = req.getHeader("X-Request-ID");
    try {
      UUID.fromString(trace);
    } catch (Exception e) {
      trace = UUID.randomUUID().toString();
    }
    MDC.put("request_id", trace);
    res.setHeader("X-Request-ID", trace);
    long start = System.nanoTime();
    try {
      chain.doFilter(req, res);
    } finally {
      if (!req.getRequestURI().startsWith("/health/"))
        log.info(
            "request_id={} method={} path={} status={} duration_ms={}",
            trace,
            req.getMethod(),
            req.getRequestURI()
                .replaceAll("/api/v1/(media|previews)/[^/]+", "/api/v1/$1/[redacted]"),
            res.getStatus(),
            (System.nanoTime() - start) / 1000000);
      MDC.remove("request_id");
    }
  }
}
