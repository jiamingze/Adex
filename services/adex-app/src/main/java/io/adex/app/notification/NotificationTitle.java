package io.adex.app.notification;

/** Short task context suitable for in-app and user-requested lock-screen titles. */
public final class NotificationTitle {
  private NotificationTitle() {}

  public static String compact(Object value) {
    if (!(value instanceof String text)) return "";
    var clean = new StringBuilder();
    text.codePoints()
        .filter(c -> !Character.isISOControl(c) && Character.getType(c) != Character.FORMAT)
        .forEach(c -> clean.appendCodePoint(Character.isWhitespace(c) ? ' ' : c));
    String title = clean.toString().strip();
    int length = title.codePointCount(0, title.length());
    return length > 28 ? title.substring(0, title.offsetByCodePoints(0, 28)) + "…" : title;
  }

  public static String completed(Object value) {
    return label(value, "已完成");
  }

  public static String label(Object value, String status) {
    String title = compact(value);
    return title.isBlank() ? "任务" + status : title + " · " + status;
  }
}
