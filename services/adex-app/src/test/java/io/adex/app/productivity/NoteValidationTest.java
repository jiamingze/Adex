package io.adex.app.productivity;

import static org.junit.jupiter.api.Assertions.*;

import java.util.Map;
import org.junit.jupiter.api.Test;

class NoteValidationTest {
  @Test
  void permitsEmptyBodyAndPreservesPlainText() {
    assertEquals("", NoteService.content(Map.of("content", "")));
    assertEquals(
        "<script>text</script>", NoteService.content(Map.of("content", "<script>text</script>")));
  }

  @Test
  void rejectsNonTextAndOversizedBodies() {
    assertThrows(RuntimeException.class, () -> NoteService.content(Map.of("content", 42)));
    assertThrows(
        RuntimeException.class, () -> NoteService.content(Map.of("content", "x".repeat(100001))));
  }
}
