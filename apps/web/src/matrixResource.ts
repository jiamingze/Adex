import { request } from "./api";
import type { MatrixTask } from "./assistantApi";
import { createReadResource } from "./readResource";

export const matrixResource = createReadResource<{ items: MatrixTask[] }>(
  (signal) => request("/matrix", "GET", undefined, undefined, { signal }),
);
// No localStorage/IndexedDB: never expose another account's private task snapshot.
window.addEventListener("adex:session-changed", () => matrixResource.reset());
