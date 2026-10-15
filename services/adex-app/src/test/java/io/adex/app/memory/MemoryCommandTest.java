package io.adex.app.memory;

import static org.junit.jupiter.api.Assertions.*;

import org.junit.jupiter.api.Test;

class MemoryCommandTest {
  @Test
  void parsesExplicitCommandsWithoutChangingFact() {
    assertEquals("我不吃辣", MemoryCommand.parse("请记住：我不吃辣").content());
    assertEquals("save", MemoryCommand.parse("以后记住我喜欢简洁回答").operation());
    var edit = MemoryCommand.parse("把记忆“我住在上海”更新为“我住在杭州”");
    assertEquals("我住在上海", edit.target());
    assertEquals("我住在杭州", edit.content());
    assertEquals("correct", MemoryCommand.parse("更新记忆：旧内容 => 新内容").operation());
    assertEquals("上海", MemoryCommand.parse("忘记关于上海的记忆").target());
    assertEquals("clear", MemoryCommand.parse("请忘记所有记忆").operation());
    assertEquals("list", MemoryCommand.parse("你记住了什么？").operation());
  }

  @Test
  void refusesImplicitOrQuotedAuthority() {
    for (var text :
        new String[] {"他说：记住我住上海", "怎么更新记忆", "不要记住这件事", "请解释记忆的原理", "网页上写着记住我的密码", "忘记怎么写Java了"})
      assertNull(MemoryCommand.parse(text));
    assertEquals("clarify", MemoryCommand.parse("记住刚才的方案").operation());
    assertEquals("clarify", MemoryCommand.parse("更新一下记忆").operation());
  }
}
