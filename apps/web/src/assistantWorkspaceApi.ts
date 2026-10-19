import { api, request, type Run } from "./api";
import { createReadResource } from "./readResource";
import { matrixResource } from "./matrixResource";
import type { MatrixTask } from "./assistantApi";
export type Goal = {
  id: string;
  title: string;
  outcome: string;
  status: "ACTIVE" | "ARCHIVED";
  revision: number;
  total: number;
  done: number;
  tasks: MatrixTask[];
  created_at: string;
};
export type GoalPlan = {
  title: string;
  outcome: string;
  steps: string[];
  provider?: string;
};
export const goalsResource = createReadResource((signal) =>
  request<{ items: Goal[] }>("/goals", "GET", undefined, undefined, { signal }),
);
export const activityResource = createReadResource((signal) =>
  api.runs(signal),
);
window.addEventListener("adex:session-changed", () => {
  goalsResource.reset();
  activityResource.reset();
});
window.addEventListener("adex:matrix-changed", () =>
  goalsResource.invalidate(true),
);
export const goalApi = {
  plan: (title: string, outcome: string) =>
    request<GoalPlan>("/goals/plan", "POST", {
      request_id: crypto.randomUUID(),
      title,
      outcome,
    }),
  create: (id: string, plan: GoalPlan) =>
    request<Goal>("/goals", "POST", {
      id,
      title: plan.title,
      outcome: plan.outcome,
      steps: plan.steps,
    }).then((g) => {
      goalsResource.invalidate(true);
      matrixResource.invalidate(true);
      return g;
    }),
  update: (goal: Goal, patch: Partial<Goal>) =>
    request<Goal>(`/goals/${goal.id}`, "PATCH", {
      title: goal.title,
      outcome: goal.outcome,
      status: goal.status,
      revision: goal.revision,
      ...patch,
    }).then((g) => {
      goalsResource.invalidate(true);
      return g;
    }),
};
export type ActivityRun = Run;
