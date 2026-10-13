import { test } from "node:test";
import assert from "node:assert/strict";
import {
  routeFromPath,
  pagePath,
  pages,
} from "../../.local-data/client-tests/navigation.js";
import {
  focusTasks,
  isDueToday,
  awaitingAction,
  planningPrompt,
} from "../../.local-data/client-tests/todayModel.js";
test("every page restores on direct link and history", () => {
  for (const page of pages)
    assert.equal(routeFromPath(pagePath(page)).page, page);
  assert.equal(routeFromPath("/matrix/").page, "matrix");
});
test("conversation deep links stay distinct from page navigation", () => {
  const id = "52dcd853-05c2-4c5a-873c-da21659bb7e5";
  assert.deepEqual(routeFromPath(pagePath("chat", id)), {
    page: "chat",
    conversation: id,
  });
  assert.deepEqual(routeFromPath("/c/not-an-id"), {
    page: "chat",
    conversation: "",
  });
  assert.equal(routeFromPath("/assistant").conversation, "");
  assert.equal(routeFromPath("/unknown").page, "chat");
});
test("daily focus excludes completed work, ranks importance and dates without mutating source", () => {
  const item = (id, important, urgent, due_at = null, status = "TODO") => ({
    id,
    important,
    urgent,
    due_at,
    status,
  });
  const tasks = [
    item("low", false, true),
    item("plan", true, false),
    item("later", true, true, "2026-10-14T08:00:00Z"),
    item("first", true, true, "2026-10-13T08:00:00Z"),
    item("done", true, true, null, "DONE"),
  ];
  assert.deepEqual(
    focusTasks(tasks).map((t) => t.id),
    ["first", "later", "plan", "low"],
  );
  assert.equal(tasks[0].id, "low");
});
test("today uses device-local calendar day including UTC boundaries", () => {
  const now = new Date(2026, 9, 13, 10);
  assert.equal(
    isDueToday(new Date(2026, 9, 13, 23, 59).toISOString(), now),
    true,
  );
  assert.equal(isDueToday(new Date(2026, 9, 14, 0).toISOString(), now), false);
  assert.equal(isDueToday(null, now), false);
});
test("expired approvals are not pending; uncertain effects still require attention", () => {
  const actions = [
    { state: "PENDING", expires_at: "2026-10-14T00:00:00Z" },
    { state: "PENDING", expires_at: "2026-10-12T00:00:00Z" },
    { state: "APPROVED", expires_at: "2026-10-14T00:00:00Z" },
    { state: "UNKNOWN", expires_at: "2026-10-12T00:00:00Z" },
  ];
  assert.deepEqual(awaitingAction(actions, new Date("2026-10-13T00:00:00Z")), [
    actions[0],
    actions[3],
  ]);
});

test("planning draft distinguishes unavailable data, bounds context and never calls an API", () => {
  const missing = planningPrompt(
    { tasks: null, schedules: null },
    new Date("2026-10-13T00:00:00Z"),
  );
  assert.match(missing, /暂不可用/);
  assert.doesNotMatch(missing, /待办为空/);
  const tasks = Array.from({ length: 20 }, (_, i) => ({
    title: `task-${i}`,
    status: "TODO",
    important: true,
    urgent: true,
    due_at: null,
  }));
  const draft = planningPrompt(
    { tasks, schedules: [] },
    new Date("2026-10-13T00:00:00Z"),
  );
  assert.match(draft, /task-7/);
  assert.doesNotMatch(draft, /task-8/);
  assert.match(draft, /不是日历事件/);
  assert.match(draft, /再让我确认/);
});
