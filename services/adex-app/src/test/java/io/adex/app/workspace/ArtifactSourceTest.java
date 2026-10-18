package io.adex.app.workspace;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class ArtifactSourceTest {
  @Test
  void extractsOnlyKnownFencedSourcesAndPreservesBody() {
    assertEquals(
        "flowchart LR\nA-->B\n",
        ArtifactSource.fenced("intro\n```mermaid\nflowchart LR\nA-->B\n```\nend"));
    assertEquals(
        "<main>Hello</main>\r\n", ArtifactSource.fenced("```HTML \r\n<main>Hello</main>\r\n```"));
    assertEquals("plain", ArtifactSource.fenced("plain"));
    assertEquals("```python\nx\n```", ArtifactSource.fenced("```python\nx\n```"));
  }

  @Test
  void longMalformedHeadersAndMissingClosersRemainUnchanged() {
    String malformed = "```html ".repeat(12000);
    assertEquals(malformed, ArtifactSource.fenced(malformed));
    String missing = "```mermaid\n" + "A-->B\n".repeat(2000);
    assertEquals(missing, ArtifactSource.fenced(missing));
  }

  @Test
  void completeArrowTokensAreAllowedButHtmlAnglesAreNot() {
    for (String arrow : new String[] {"-->", "->>", "-->>", "->", "<--", "<->"}) {
      assertFalse(ArtifactSource.hasUnsafeAngles("sequenceDiagram\n A" + arrow + "B: hello"));
    }
    for (String text :
        new String[] {"<script>x</script>", "<!--x-->", "<<--script-->>", "A[<img src=x>]"}) {
      assertTrue(ArtifactSource.hasUnsafeAngles(text));
    }
  }
}
