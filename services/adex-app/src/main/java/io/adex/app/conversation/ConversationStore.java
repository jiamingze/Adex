package io.adex.app.conversation;

import java.util.Map;
import java.util.UUID;

/**
 * Authoritative conversation persistence and sequence allocation port. Append/event operations must
 * run in the caller's transaction holding the conversation row lock. Cache implementations cannot
 * replace this port without preserving durable fencing and ordering.
 */
public interface ConversationStore {
  Map<String, Object> own(UUID owner, UUID conv);

  long event(UUID conv, String type, Object payload);

  UUID append(UUID conv, String role, String content, String dedupe);

  Map<String, Object> send(UUID owner, UUID conv, Map<String, Object> body);

  Map<String, Object> context(UUID owner, UUID conv, long upto);

  void finish(Map<String, Object> turn, String content, Object cards);
}
