package io.adex.app.workspace;

/** Extracts an editable fenced source without backtracking on untrusted model output. */
final class ArtifactSource {
  private ArtifactSource() {}

  static String fenced(String text) {
    int cursor = 0;
    while (cursor < text.length()) {
      int opening = text.indexOf("```", cursor);
      if (opening < 0) break;
      int newline = text.indexOf('\n', opening + 3);
      if (newline < 0) break;
      String language = text.substring(opening + 3, newline).strip();
      if (language.equalsIgnoreCase("html") || language.equalsIgnoreCase("mermaid")) {
        int closing = text.indexOf("```", newline + 1);
        return closing < 0 ? text : text.substring(newline + 1, closing);
      }
      // Consume the whole invalid header once; repeated fence near-misses stay linear.
      cursor = newline + 1;
    }
    return text;
  }

  /** Recognize fixed arrow tokens; never remove HTML-like text before validating it. */
  static boolean hasUnsafeAngles(String source) {
    String[] arrows = {"-->>", "->>", "-->", "<--", "<->", "->"};
    int cursor = 0;
    while (cursor < source.length()) {
      String matched = null;
      for (String arrow : arrows) {
        if (source.startsWith(arrow, cursor)) {
          matched = arrow;
          break;
        }
      }
      if (matched != null) cursor += matched.length();
      else if (source.charAt(cursor) == '<' || source.charAt(cursor) == '>') return true;
      else cursor++;
    }
    return false;
  }
}
