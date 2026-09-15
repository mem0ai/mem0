import { createHash } from "node:crypto";
import { realpathSync } from "node:fs";
import { isAbsolute } from "node:path";

export {
  entityAddParams as resolveAddParams,
  entitySearchFilters as resolveSearchFilters,
} from "../../agent-plugin-core/typescript/src/identity.ts";
export type { EntityParams } from "../../agent-plugin-core/typescript/src/identity.ts";

export function resolveWorkspaceId(cwd: string | undefined): string {
  if (!cwd || !isAbsolute(cwd)) {
    throw new Error("Workspace memory scope requires an absolute session workspace path.");
  }
  return `deepseek-workspace-${createHash("sha256").update(realpathSync(cwd)).digest("hex")}`;
}
