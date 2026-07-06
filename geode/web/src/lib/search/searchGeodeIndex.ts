import { spawnSync } from "node:child_process";
import path from "node:path";

import { GEODE_READ_INDEX_PATH, REPOSITORY_ROOT } from "@/lib/paths";
import type { RegulationSearchResult } from "@/lib/search/types";

export type GeodeSearchResult = RegulationSearchResult & {
  layer?: string;
  entityType?: string;
};

export function searchGeodeIndex(query: string, limit = 8): GeodeSearchResult[] {
  const python = process.env.PYTHON ?? "python";
  const pythonPath = [REPOSITORY_ROOT, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter);
  const result = spawnSync(
    python,
    [
      "-m",
      "geode.web.query_index",
      "--database",
      GEODE_READ_INDEX_PATH,
      "--query",
      query,
      "--limit",
      String(limit),
    ],
    {
      cwd: REPOSITORY_ROOT,
      encoding: "utf8",
      env: {
        ...process.env,
        PYTHONPATH: pythonPath,
      },
      maxBuffer: 1024 * 1024 * 4,
    },
  );

  if (result.error) {
    throw result.error;
  }

  if (result.status !== 0) {
    throw new Error(result.stderr || "Geode read-index query failed.");
  }

  return JSON.parse(result.stdout) as GeodeSearchResult[];
}
