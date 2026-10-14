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
  assert.equal(routeFromPath("/notes").page, "workspace");
  assert.equal(routeFromPath("/workspace").page, "workspace");
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

test("task read deadline bounds a transport that never responds", async () => {
  const { createReadResource } = await import(
    "../../.local-data/client-tests/readResource.js"
  );
  const resource = createReadResource(() => new Promise(() => {}), {
    timeoutMs: 15,
  });
  await assert.rejects(resource.load(), /READ_TIMEOUT/);
  assert.equal(resource.getSnapshot().loading, false);
  assert.equal(resource.getSnapshot().data, null);
});
test("navigation shares fresh snapshots and one concurrent read", async () => {
  const { createReadResource } = await import(
    "../../.local-data/client-tests/readResource.js"
  );
  let calls = 0;
  const resource = createReadResource(async () => {
    calls++;
    return { items: ["owned task"] };
  });
  const one = resource.load(),
    two = resource.load();
  assert.equal(one, two);
  await one;
  await resource.load();
  assert.equal(calls, 1);
  assert.deepEqual(resource.getSnapshot().data, { items: ["owned task"] });
});
test("session reset cancels an old read and cannot resurrect another account's data", async () => {
  const { createReadResource } = await import(
    "../../.local-data/client-tests/readResource.js"
  );
  let finish;
  let calls = 0;
  const resource = createReadResource(() =>
    ++calls === 1
      ? new Promise((resolve) => (finish = resolve))
      : Promise.resolve("new owner"),
  );
  const old = resource.load();
  await Promise.resolve();
  resource.reset();
  await assert.rejects(old, /READ_CANCELLED/);
  await resource.load();
  finish("previous owner");
  await Promise.resolve();
  assert.equal(resource.getSnapshot().data, "new owner");
});
test("revalidation retains visible tasks; failed reads can be retried", async () => {
  const { createReadResource } = await import(
    "../../.local-data/client-tests/readResource.js"
  );
  let fail = false;
  const resource = createReadResource(async () => {
    if (fail) throw new Error("NETWORK");
    return ["task"];
  });
  await resource.load();
  fail = true;
  const retry = resource.load(true);
  assert.deepEqual(resource.getSnapshot().data, ["task"]);
  await assert.rejects(retry, /NETWORK/);
  assert.equal(resource.getSnapshot().loading, false);
  fail = false;
  assert.deepEqual(await resource.load(true), ["task"]);
});

test("agenda excludes ended/cancelled events, retains ongoing meetings and sorts by start", async () => {
  const { upcomingAgenda } = await import(
    "../../.local-data/client-tests/calendarAgenda.js"
  );
  const event = (id, start, end, status) => ({
    id,
    summary: id,
    status,
    start: { dateTime: start },
    end: { dateTime: end },
  });
  const result = upcomingAgenda(
    [
      event("next", "2026-10-14T03:00:00Z", "2026-10-14T04:00:00Z"),
      event("ongoing", "2026-10-14T01:00:00Z", "2026-10-14T02:30:00Z"),
      event("ended", "2026-10-14T00:00:00Z", "2026-10-14T02:00:00Z"),
      event(
        "cancelled",
        "2026-10-14T03:00:00Z",
        "2026-10-14T04:00:00Z",
        "cancelled",
      ),
    ],
    new Date("2026-10-14T02:00:00Z"),
  );
  assert.deepEqual(
    result.items.map((e) => e.id),
    ["ongoing", "next"],
  );
  assert.equal(result.items[0].ongoing, true);
});
test("agenda handles exclusive all-day end and flags malformed or unzoned dates", async () => {
  const { upcomingAgenda } = await import(
    "../../.local-data/client-tests/calendarAgenda.js"
  );
  const result = upcomingAgenda(
    [
      {
        id: "today",
        start: { date: "2026-10-14" },
        end: { date: "2026-10-15" },
      },
      {
        id: "past",
        start: { date: "2026-10-13" },
        end: { date: "2026-10-14" },
      },
      { id: "bad", start: { date: "2026-02-30" }, end: { date: "2026-03-01" } },
      {
        id: "naive",
        start: { dateTime: "2026-10-14T10:00:00" },
        end: { dateTime: "2026-10-14T11:00:00" },
      },
    ],
    new Date(2026, 9, 14, 10),
  );
  assert.deepEqual(
    result.items.map((e) => e.id),
    ["today"],
  );
  assert.equal(result.items[0].allDay, true);
  assert.equal(result.invalid, 2);
});

test("calendar organizer/location are optional provider metadata, never invented", async () => {
  const { upcomingAgenda } = await import(
    "../../.local-data/client-tests/calendarAgenda.js"
  );
  const { items } = upcomingAgenda(
    [
      {
        id: "metadata",
        summary: "Meeting",
        organizer: " Alice ",
        location: " Room 3 ",
        start: { dateTime: "2026-10-14T10:00:00Z" },
        end: { dateTime: "2026-10-14T11:00:00Z" },
      },
      {
        id: "private",
        start: { dateTime: "2026-10-14T12:00:00Z" },
        end: { dateTime: "2026-10-14T13:00:00Z" },
      },
    ],
    new Date("2026-10-14T09:00:00Z"),
  );
  assert.equal(items[0].organizer, "Alice");
  assert.equal(items[0].location, "Room 3");
  assert.equal(items[1].organizer, undefined);
  assert.equal(items[1].location, undefined);
});
