import { mkdirSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
mkdirSync(".local-data/client-tests", { recursive: true });
writeFileSync(".local-data/client-tests/package.json", '{"type":"module"}\n');
for (const [command, args] of [
  [
    "pnpm",
    [
      "exec",
      "tsc",
      "apps/web/src/navigation.ts",
      "apps/web/src/todayModel.ts",
      "apps/web/src/readResource.ts",
      "apps/web/src/calendarAgenda.ts",
      "--outDir",
      ".local-data/client-tests",
      "--target",
      "ES2022",
      "--module",
      "ES2022",
      "--skipLibCheck",
      "--strict",
    ],
  ],
  [process.execPath, ["--test", "tests/client/experience.test.mjs"]],
]) {
  const result = spawnSync(command, args, { stdio: "inherit" });
  if (result.status !== 0) process.exit(result.status ?? 1);
}
