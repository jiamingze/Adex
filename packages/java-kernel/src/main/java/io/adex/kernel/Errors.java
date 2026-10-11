package io.adex.kernel;

import java.util.Map;
import org.springframework.dao.DataAccessException;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestControllerAdvice
public class Errors {
  @ExceptionHandler(Kernel.Problem.class)
  public ResponseEntity<?> problem(Kernel.Problem e) {
    return ResponseEntity.status(e.status)
        .body(Map.of("code", e.code, "request_id", Kernel.id().toString()));
  }

  @ExceptionHandler(DataAccessException.class)
  public ResponseEntity<?> database(DataAccessException e) {
    return ResponseEntity.status(503)
        .body(Map.of("code", "DATABASE_UNAVAILABLE", "request_id", Kernel.id().toString()));
  }

  @ExceptionHandler({
    IllegalArgumentException.class,
    org.springframework.http.converter.HttpMessageNotReadableException.class
  })
  public ResponseEntity<?> input(Exception e) {
    return ResponseEntity.badRequest()
        .body(Map.of("code", "INVALID_INPUT", "request_id", Kernel.id().toString()));
  }
}
