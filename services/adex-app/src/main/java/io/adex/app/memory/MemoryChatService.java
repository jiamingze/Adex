package io.adex.app.memory;

import io.adex.app.conversation.ConversationStore;
import io.adex.kernel.Kernel;
import java.util.*;
import org.springframework.stereotype.Service;

/** Durable explicit memory commands. The reply and mutation share the existing Turn transaction. */
@Service
public class MemoryChatService {
  private final Kernel k;
  private final MemoryService memory;
  private final ConversationStore chat;

  public MemoryChatService(Kernel k, MemoryService memory, ConversationStore chat) {
    this.k = k;
    this.memory = memory;
    this.chat = chat;
  }

  public boolean handle(Map<String, Object> turn) {
    String text =
        String.valueOf(
            k.row("SELECT content FROM messages WHERE id=? AND role='user'", turn.get("id"))
                .get("content"));
    var command = MemoryCommand.parse(text);
    if (command == null) return false;
    k.tx.executeWithoutResult(
        tx -> {
          UUID owner = (UUID) turn.get("owner_id"), conv = (UUID) turn.get("conversation_id");
          // Match the context/deletion lock order. Never mutate before the live-attempt fence.
          var user = k.row("SELECT * FROM users WHERE id=? FOR UPDATE", owner);
          var conversation =
              k.row(
                  "SELECT deleted_at FROM conversations WHERE id=? AND owner_id=? FOR UPDATE",
                  conv,
                  owner);
          var live =
              k.db.queryForList(
                  "SELECT id FROM turns WHERE id=? AND owner_id=? AND epoch=? AND attempt_id=? AND status='RUNNING' AND lease_until>clock_timestamp() FOR UPDATE",
                  turn.get("id"),
                  owner,
                  turn.get("epoch"),
                  turn.get("attempt_id"));
          if (live.isEmpty() || conversation.get("deleted_at") != null)
            throw Kernel.error(409, "STALE_EXECUTION");
          String reply = apply(owner, turn, user, command);
          turn.put(
              "memory_revision",
              k.row("SELECT memory_revision FROM users WHERE id=?", owner).get("memory_revision"));
          chat.finish(turn, reply, List.of());
        });
    return true;
  }

  private String apply(
      UUID owner, Map<String, Object> turn, Map<String, Object> user, MemoryCommand command) {
    if (Boolean.TRUE.equals(user.get("is_guest"))) return "登录后才能保存和管理长期记忆。当前对话仍可继续。";
    if (command.operation().equals("clarify"))
      return "请明确要保存或修改的内容，例如：记住：我喜欢清淡饮食；把记忆“我住在上海”更新为“我住在杭州”。";
    var items =
        k.db.queryForList(
            "SELECT id,content FROM memories WHERE owner_id=? AND deleted_at IS NULL ORDER BY created_at DESC",
            owner);
    if (command.operation().equals("list")) {
      if (items.isEmpty()) return "目前没有保存的长期记忆。你可以说“记住：…”来添加。";
      StringBuilder result = new StringBuilder("已保存的长期记忆（" + items.size() + "条）：\n\n");
      for (var item : items.stream().limit(20).toList())
        result.append("- ").append(item.get("content")).append("\n");
      return result + (items.size() > 20 ? "\n其余内容可在个人记忆页面查看。" : "\n你可以明确要求修改或忘记其中一条。");
    }
    if (Set.of("save", "correct").contains(command.operation())) {
      if (Boolean.FALSE.equals(
          k.decode(String.valueOf(user.get("settings"))).get("memory_enabled")))
        return "你已关闭记忆，尚未保存。请在设置中开启记忆后重试。";
      if (command.content().isBlank() || command.content().length() > 2000)
        return "请提供1至2000字的明确记忆内容，本次未保存。";
      if (command
          .content()
          .matches("(?is).*(?:密码|验证码|api.?key|access.?token|私钥|password|sk-[a-z0-9]).*"))
        return "请不要将密码、验证码或密钥保存为长期记忆。本次未保存。";
      if (k.db.queryForObject(
              "SELECT count(*) FROM memory_tombstones WHERE owner_id=? AND content_hash=?",
              Integer.class,
              owner,
              Kernel.memoryHash(command.content()))
          > 0) return "这条内容已被你遗忘，为避免旧记忆复活，本次没有重新保存。";
    }
    Map<String, Object> body =
        Map.of("content", command.content(), "source_message_id", turn.get("id").toString());
    if (command.operation().equals("save")) {
      memory.save(owner, body);
      return "已记住：" + command.content() + "\n\n开启记忆时，我会在后续对话中参考这条信息。你也可以随时要求修改或忘记。";
    }
    if (command.operation().equals("clear")) {
      for (var item : items) memory.remove(owner, (UUID) item.get("id"));
      return "已清空长期记忆（" + items.size() + "条）。历史聊天不会因此删除。";
    }
    if (command.target().isBlank()) return "请明确要忘记哪条记忆，例如：忘记关于上海的记忆。";
    var matches = items.stream().filter(m -> m.get("content").equals(command.target())).toList();
    if (matches.isEmpty())
      matches =
          items.stream()
              .filter(m -> String.valueOf(m.get("content")).contains(command.target()))
              .toList();
    if (matches.isEmpty()) return "没有找到匹配的长期记忆，本次未修改。可以先问“你记住了什么”，再指定原内容。";
    if (matches.size() != 1) return "找到" + matches.size() + "条相关记忆，请指定更完整的原内容，本次未修改。";
    var match = matches.getFirst();
    if (command.operation().equals("forget")) {
      memory.remove(owner, (UUID) match.get("id"));
      return "已忘记这条长期记忆。它不会再通过旧摘要或搜索索引恢复。历史聊天记录仍保留。";
    }
    if (match.get("content").equals(command.content())) return "这条记忆已是该内容，无需修改。";
    memory.correct(owner, (UUID) match.get("id"), body);
    return "已更新记忆：" + command.content() + "\n\n旧内容已失效，后续对话会参考更新后的信息。";
  }
}
