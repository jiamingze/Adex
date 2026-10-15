# Conversational memory (M03 extension)

App remains the authoritative memory owner. Explicit user messages can save, correct,
forget or list long-term memories. Ordinary discussion, quoted commands, search results
and model output cannot authorize mutations. Conservative command grammar is intentional:
ambiguous targets return clarification rather than guessed edits.

Supported forms include `请记住：我喜欢清淡饮食`, `以后记住我喜欢简洁回答`,
`把记忆“我住在上海”更新为“我住在杭州”`, `更新记忆：旧内容 => 新内容`,
`忘记关于上海的记忆`, `忘记所有记忆`, and `你记住了什么`.
Correction/deletion first tries an exact match, then a unique literal substring;
multiple matches require a more specific instruction. No model output proves persistence.

No schema or public API migration is required. Existing memory CRUD, source_refs,
revision, tombstones, forgetting watermark and search outbox remain authoritative.
Explicit chat commands execute before Agent routing. Lock order is user → conversation
→ turn, with live epoch/attempt/lease checked before mutation. Memory writes, turn
completion and assistant receipt commit in one short PostgreSQL transaction; a crash
cannot commit an operation without its durable reply. Repeated client IDs use the
existing Turn identity. No remote model call takes place under locks.

Guest accounts cannot persist these commands. Disabled memory blocks saves/corrections;
listing and deletion remain available. A forgotten fact cannot be silently reintroduced,
including by delayed extraction. Existing asynchronous extraction becomes summary-only:
explicit memory writes have exactly one authority. Corrections keep old tombstoned rows
and source provenance. New conversations use the existing revision-aware memory context.

This is persistent personalization, not model-weight training or automatic self-modifying
code. Only explicit facts are saved; unsupported/ambiguous wording requires clarification.
Broad semantic profile inference and autonomous memory merging are not enabled.

## Verification and operation

Run `make build`, `make test`, `make check-style`, `make test-integration`, and
`uv run python scripts/check_secrets.py`. Integration tests use an isolated database,
mock normal chat and synthetic facts; the command path does not invoke any model.
Tests cover provenance, client-message deduplication, correction, cross-conversation
context, forgetting, delayed-job non-resurrection, ambiguous matches, disabled memory,
credential-content refusal, guest restrictions, inspection and owner-scoped clearing.

No iOS bundle changes are required: the existing chat SSE completion event refreshes
the durable response. Existing users retain saved memories. A backend restart activates
the new command handler. Inspect and edit all records from the personal-memory page.
Context retrieval remains bounded to the latest 20 confirmed facts; the chat inspection
reply shows at most 20 facts and points to the memory page for the remaining records.
Do not describe this bound as unlimited semantic recall.

Observed on 2026-10-16: Java 11 unit tests, Agent 42 tests, Tools 63 tests and
90-operation OpenAPI checks passed via `make test`; production build, Spotless/Ruff,
architecture checks, secret scan and diff whitespace check passed. Full isolated
integration suite: 51 passed. Local App/Automation/Agent/Tools readiness all HTTP 200.
