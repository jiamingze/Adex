package io.adex.app.memory;

import java.util.regex.Pattern;

/** Explicit user-command grammar; never applied to tool output or assistant messages. */
public record MemoryCommand(String operation, String target, String content) {
  private static final Pattern ADD =
      Pattern.compile(
          "^(?:请|请你|帮我|麻烦你|请帮我)?(?:以后)?(?:记住|记一下|记下来|记着)(?:一下)?[：:，,\\s]*(.+)$", Pattern.DOTALL);
  private static final Pattern EDIT =
      Pattern.compile(
          "^(?:请|请你|帮我|请帮我)?(?:把|将)(?:记忆|记住的内容)[：:，,\\s]*(.+?)(?:更新为|修改为|改成|改为|更正为)[：:，,\\s]*(.+)$",
          Pattern.DOTALL);
  private static final Pattern ARROW =
      Pattern.compile(
          "^(?:请|请你|帮我|请帮我)?(?:更新|修改|更正)记忆[：:，,\\s]*(.+?)\\s*(?:=>|→)\\s*(.+)$", Pattern.DOTALL);
  private static final Pattern FORGET =
      Pattern.compile("^(?:请|请你|帮我|请帮我)?(?:忘记|删除记忆|删除这条记忆|删除关于)[：:，,\\s]*(.*)$", Pattern.DOTALL);

  public static MemoryCommand parse(String text) {
    String value = text.strip();
    if (value.matches("(?:请)?(?:你记住了什么|你记得什么|查看记忆|查看我的记忆|列出(?:我的|所有)?记忆)[？?。！!]*"))
      return new MemoryCommand("list", "", "");
    if (value.matches("(?:请|请你|帮我|请帮我)?(?:忘记|删除|清空)(?:我的)?(?:所有|全部)记忆[。！!]*"))
      return new MemoryCommand("clear", "", "");
    for (var pattern : new Pattern[] {EDIT, ARROW}) {
      var match = pattern.matcher(value);
      if (match.matches())
        return new MemoryCommand("correct", clean(match.group(1)), clean(match.group(2)));
    }
    var add = ADD.matcher(value);
    if (add.matches()) {
      String fact = clean(add.group(1));
      if (fact.matches("(?:刚才|之前|上面|这些|这个|这件事|我的偏好|什么).*"))
        return new MemoryCommand("clarify", "", "");
      return new MemoryCommand("save", "", fact);
    }
    if (value.matches("^(?:请|请你|帮我)?忘记(?:怎么|如何|什么是|了).*")) return null;
    var forget = FORGET.matcher(value);
    if (forget.matches()) {
      String target =
          clean(forget.group(1)).replaceFirst("^关于", "").replaceFirst("(?:的记忆|这条记忆)$", "").strip();
      return new MemoryCommand("forget", target, "");
    }
    if (value.matches("(?:请|请你|帮我|请帮我)?(?:更新|修改|更正)(?:一下)?记忆.*"))
      return new MemoryCommand("clarify", "", "");
    return null;
  }

  private static String clean(String value) {
    return value.strip().replaceAll("^[“\"‘']|[”\"’']$", "").strip();
  }
}
