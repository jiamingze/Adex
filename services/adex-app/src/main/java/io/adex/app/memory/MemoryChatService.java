package io.adex.app.memory;

import io.adex.app.conversation.ConversationStore;
import io.adex.kernel.Kernel;
import java.util.*;
import org.springframework.stereotype.Service;

/** Model proposes normalized facts; only App validates and commits under the live Turn fence. */
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
    UUID id = (UUID) turn.get("id"), owner = (UUID) turn.get("owner_id");
    var stored =
        k.tx.execute(
            tx -> {
              var user = lock(turn);
              var old =
                  k.db.queryForList(
                      "SELECT * FROM memory_turn_plans WHERE turn_id=? AND owner_id=?", id, owner);
              if (!old.isEmpty()) return old.getFirst();
              var source = k.row("SELECT content,seq FROM messages WHERE id=? AND role='user'", id);
              boolean allowed =
                  String.valueOf(source.get("content")).length() <= 12000
                      && !Boolean.TRUE.equals(user.get("is_guest"))
                      && !Boolean.FALSE.equals(
                          k.decode(String.valueOf(user.get("settings"))).get("memory_enabled"));
              var input = new LinkedHashMap<String, Object>();
              input.put("latest", String.valueOf(source.get("content")));
              input.put("memory_revision", user.get("memory_revision"));
              input.put("enabled", allowed);
              input.put(
                  "recent",
                  allowed
                      ? k.db.queryForList(
                          "SELECT role,left(content,1800) AS content FROM (SELECT role,content,seq FROM messages WHERE conversation_id=? AND seq<? AND (?::timestamptz IS NULL OR created_at>?::timestamptz) ORDER BY seq DESC LIMIT 6) m ORDER BY seq",
                          turn.get("conversation_id"),
                          source.get("seq"),
                          user.get("forgotten_before"),
                          user.get("forgotten_before"))
                      : List.of());
              input.put(
                  "memories",
                  allowed
                      ? k.db.queryForList(
                          "SELECT id,revision,left(content,600) AS content,length(content)>600 AS truncated FROM memories WHERE owner_id=? AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 200",
                          owner)
                      : List.of());
              // Bound total planning tokens as memory grows, not just the number of rows.
              var bounded = new ArrayList<Object>();
              int remaining = 18000;
              for (Object candidate : (List<?>) input.get("memories")) {
                int size = k.encode(candidate).length();
                if (size > remaining) break;
                bounded.add(candidate);
                remaining -= size;
              }
              input.put("memories", bounded);
              var none = Map.of("mode", "none", "operations", List.of());
              k.db.update(
                  "INSERT INTO memory_turn_plans(turn_id,owner_id,input,proposal) VALUES(?,?,?::jsonb,?::jsonb)",
                  id,
                  owner,
                  k.encode(input),
                  allowed ? null : k.encode(none));
              return k.row("SELECT * FROM memory_turn_plans WHERE turn_id=?", id);
            });
    var input = k.decode(String.valueOf(stored.get("input")));
    if (stored.get("proposal") == null) {
      Map<String, Object> proposal;
      try {
        if (((Number) input.get("memory_revision")).longValue()
            != ((Number)
                    k.row("SELECT memory_revision FROM users WHERE id=?", owner)
                        .get("memory_revision"))
                .longValue()) throw Kernel.error(409, "MEMORY_PLAN_STALE");
        proposal =
            k.call(
                "agent",
                "memory:plan",
                owner,
                id,
                "POST",
                "/internal/agent/memory-plan",
                Map.of(
                    "owner_id",
                    owner,
                    "turn_id",
                    id,
                    "snapshot",
                    input,
                    "model",
                    turn.getOrDefault("model", "")));
      } catch (Exception failure) {
        // Never fall back to storing raw text or repeatedly dispatch an uncertain paid call.
        proposal =
            Map.of(
                "mode",
                "none",
                "operations",
                List.of(),
                "unavailable",
                true,
                "failure_code",
                failure instanceof Kernel.Problem problem
                    ? problem.code
                    : "MEMORY_PLAN_UNAVAILABLE");
      }
      k.db.update(
          "UPDATE memory_turn_plans SET proposal=?::jsonb WHERE turn_id=? AND owner_id=? AND proposal IS NULL",
          k.encode(proposal),
          id,
          owner);
    }
    var proposal = proposal(id);
    if (!"manage".equals(proposal.get("mode"))) return false;
    k.tx.executeWithoutResult(
        tx -> {
          var user = lock(turn);
          String receipt = apply(turn, user, proposal, input);
          complete(turn, receipt, List.of());
        });
    return true;
  }

  public void finish(Map<String, Object> turn, String content, Object cards) {
    k.tx.executeWithoutResult(
        tx -> {
          var user = lock(turn);
          // A concurrent forget invalidates the streamed answer as well as its proposed facts.
          if (((Number) user.get("memory_revision")).longValue()
              != ((Number) turn.get("memory_revision")).longValue())
            throw Kernel.error(409, "MEMORY_REVISION_CHANGED");
          var saved =
              k.row(
                  "SELECT input,proposal FROM memory_turn_plans WHERE turn_id=? AND owner_id=?",
                  turn.get("id"),
                  turn.get("owner_id"));
          var proposed = k.decode(String.valueOf(saved.get("proposal")));
          String receipt =
              "learn".equals(proposed.get("mode"))
                  ? apply(turn, user, proposed, k.decode(String.valueOf(saved.get("input"))))
                  : Boolean.TRUE.equals(proposed.get("unavailable")) ? "本次记忆整理暂时不可用，未更新长期记忆。" : "";
          complete(turn, content + (receipt.isBlank() ? "" : "\n\n---\n\n" + receipt), cards);
        });
  }

  private Map<String, Object> proposal(UUID turn) {
    return k.decode(
        String.valueOf(
            k.row("SELECT proposal FROM memory_turn_plans WHERE turn_id=?", turn).get("proposal")));
  }

  private Map<String, Object> lock(Map<String, Object> turn) {
    // Same global order as context/forget/finish. No model or network execution under locks.
    var user = k.row("SELECT * FROM users WHERE id=? FOR UPDATE", turn.get("owner_id"));
    var conv =
        k.row(
            "SELECT deleted_at FROM conversations WHERE id=? AND owner_id=? FOR UPDATE",
            turn.get("conversation_id"),
            turn.get("owner_id"));
    var live =
        k.db.queryForList(
            "SELECT id FROM turns WHERE id=? AND owner_id=? AND epoch=? AND attempt_id=? AND status='RUNNING' AND lease_until>clock_timestamp() FOR UPDATE",
            turn.get("id"),
            turn.get("owner_id"),
            turn.get("epoch"),
            turn.get("attempt_id"));
    if (live.isEmpty() || conv.get("deleted_at") != null)
      throw Kernel.error(409, "STALE_EXECUTION");
    return user;
  }

  private void complete(Map<String, Object> turn, String content, Object cards) {
    turn.put(
        "memory_revision",
        k.row("SELECT memory_revision FROM users WHERE id=?", turn.get("owner_id"))
            .get("memory_revision"));
    k.db.update(
        "UPDATE memory_turn_plans SET applied_at=now() WHERE turn_id=? AND applied_at IS NULL",
        turn.get("id"));
    chat.finish(turn, content, cards);
  }

  private String apply(
      Map<String, Object> turn,
      Map<String, Object> user,
      Map<String, Object> plan,
      Map<String, Object> input) {
    UUID owner = (UUID) turn.get("owner_id");
    if (Boolean.TRUE.equals(user.get("is_guest"))) return "登录后才能保存长期记忆。";
    if (Boolean.FALSE.equals(k.decode(String.valueOf(user.get("settings"))).get("memory_enabled")))
      return "你已关闭记忆，本次未保存或修改。";
    if (((Number) input.get("memory_revision")).longValue()
        != ((Number) user.get("memory_revision")).longValue()) return "记忆刚刚发生变化，本次未修改，请重新确认。";
    if (!(plan.get("operations") instanceof List<?> operations)
        || operations.isEmpty()
        || operations.size() > 3) return "没有需要保存的长期信息。";
    String latest = String.valueOf(input.get("latest"));
    var targets = new HashSet<UUID>();
    // Validate the whole batch before any write. The proposal itself is never a receipt.
    for (Object raw : operations) {
      if (!(raw instanceof Map<?, ?> op)) return "记忆整理结果无效，本次未保存。";
      String action = String.valueOf(op.get("operation")),
          evidence = String.valueOf(op.get("evidence")),
          content = String.valueOf(op.getOrDefault("content", null));
      if (!Set.of("save", "correct", "forget", "clear", "list", "clarify").contains(action)
          || !(op.get("confidence") instanceof Number confidence)
          || confidence.doubleValue() < 0.9
          || evidence.isBlank()
          || evidence.equals("null")
          || !latest.contains(evidence)) return "记忆内容还不够明确，本次未修改。请补充需要保留的信息。";
      if (Set.of("clarify", "clear", "list").contains(action) && operations.size() != 1)
        return "记忆操作存在歧义，本次未修改，请分开确认。";
      if ("learn".equals(plan.get("mode")) && !Set.of("save", "correct").contains(action))
        return "";
      if ("sensitive".equals(op.get("category"))) return "这涉及敏感信息，请在个人记忆页面自主确认和管理，本次未自动保存。";
      if (Set.of("save", "correct").contains(action)) {
        if (content.isBlank()
            || content.equals("null")
            || content.length() > 2000
            || sensitive(content)
            || sensitive(evidence)) return "这条信息不适合自动保存为长期记忆，本次未保存。";
        if (k.db.queryForObject(
                "SELECT count(*) FROM memory_tombstones WHERE owner_id=? AND content_hash=?",
                Integer.class,
                owner,
                Kernel.memoryHash(content))
            > 0) return "这条内容已被你遗忘，为避免旧记忆复活，本次没有重新保存。";
      }
      if (Set.of("correct", "forget").contains(action)) {
        UUID target;
        try {
          target = Kernel.uuid(op.get("target_id"));
        } catch (Exception invalid) {
          return "没有唯一匹配的原记忆，本次未修改。";
        }
        boolean observed =
            input.get("memories") instanceof List<?> observedMemories
                && observedMemories.stream()
                    .anyMatch(
                        value ->
                            value instanceof Map<?, ?> item
                                && target.toString().equals(String.valueOf(item.get("id"))));
        if (!observed) return "原记忆未出现在本次整理范围内，本次未修改。";
        var found =
            k.db.queryForList(
                "SELECT revision,content FROM memories WHERE id=? AND owner_id=? AND deleted_at IS NULL",
                target,
                owner);
        if (!targets.add(target)
            || found.isEmpty()
            || !(op.get("target_revision") instanceof Number revision)
            || ((Number) found.getFirst().get("revision")).longValue() != revision.longValue())
          return "原记忆已变化或无法唯一确定，本次未修改。";
      }
    }
    var receipts = new ArrayList<String>();
    for (Object raw : operations) {
      var op = (Map<?, ?>) raw;
      String action = String.valueOf(op.get("operation")),
          content = String.valueOf(op.get("content"));
      switch (action) {
        case "save" -> {
          memory.save(
              owner, Map.of("content", content, "source_message_id", turn.get("id").toString()));
          receipts.add("已记住：" + content);
        }
        case "correct" -> {
          UUID target = Kernel.uuid(op.get("target_id"));
          var old = k.row("SELECT content FROM memories WHERE id=? AND owner_id=?", target, owner);
          if (!content.equals(old.get("content")))
            memory.correct(
                owner,
                target,
                Map.of("content", content, "source_message_id", turn.get("id").toString()));
          receipts.add("已更新记忆：" + content);
        }
        case "forget" -> {
          memory.remove(owner, Kernel.uuid(op.get("target_id")));
          receipts.add("已忘记这条长期记忆，旧摘要和索引不会将其恢复。历史聊天仍保留。");
        }
        case "clear" -> {
          var all =
              k.db.queryForList(
                  "SELECT id FROM memories WHERE owner_id=? AND deleted_at IS NULL", owner);
          for (var row : all) memory.remove(owner, (UUID) row.get("id"));
          receipts.add("已清空长期记忆（" + all.size() + "条）。历史聊天仍保留。");
        }
        case "list" -> {
          var all =
              k.db.queryForList(
                  "SELECT content FROM memories WHERE owner_id=? AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 20",
                  owner);
          receipts.add(
              all.isEmpty()
                  ? "目前没有保存的长期记忆。"
                  : "已保存的长期记忆：\n\n"
                      + String.join("\n", all.stream().map(m -> "- " + m.get("content")).toList()));
        }
        case "clarify" ->
            receipts.add(content.isBlank() ? "请再具体说明要保留或修改的信息，本次未修改。" : content + "\n\n本次未修改记忆。");
        default -> throw Kernel.error(400, "INVALID_MEMORY_PLAN");
      }
    }
    String receipt = String.join("\n\n", receipts);
    k.db.update("UPDATE memory_turn_plans SET receipt=? WHERE turn_id=?", receipt, turn.get("id"));
    return receipt;
  }

  private static boolean sensitive(String value) {
    return value.matches(
            "(?is).*(?:密码|验证码|api.?key|access.?token|私钥|password|sk-[a-z0-9]|诊断|患有|抑郁症|宗教信仰|政治立场|银行卡|身份证|精确地址).*")
        || value.matches(
            "(?s).*(?:(?<![A-Za-z0-9])(?:[0-9]{15,18}|1[3-9][0-9]{9})(?![A-Za-z0-9])|[\\w.+-]+@[\\w.-]+\\.[a-zA-Z]{2,}).*");
  }
}
