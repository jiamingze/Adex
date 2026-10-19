import { request } from "./api";
import { createReadResource } from "./readResource";
import type { components } from "../../../packages/contracts/core.generated";
export type AccountProfile = components["schemas"]["AccountProfile"];
export const accountProfile = createReadResource(
  (signal) =>
    request<AccountProfile>("/me", "GET", undefined, undefined, { signal }),
  { timeoutMs: 20000, freshMs: 30000 },
);
let sessionEpoch = 0;
window.addEventListener("adex:session-changed", () => {
  sessionEpoch++;
  accountProfile.reset();
});
export async function saveNickname(nickname: string) {
  const epoch = sessionEpoch;
  const profile = await request<AccountProfile>("/me", "PATCH", { nickname });
  if (epoch !== sessionEpoch) throw new Error("SESSION_CHANGED");
  accountProfile.accept(profile);
  return profile;
}
