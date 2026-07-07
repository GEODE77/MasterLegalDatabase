import path from "node:path";

export const GEODE_WEB_ROOT = process.cwd();
export const REPOSITORY_ROOT = process.env.GEODE_REPOSITORY_ROOT
  ? path.resolve(process.env.GEODE_REPOSITORY_ROOT)
  : path.resolve(GEODE_WEB_ROOT, "..", "..");

export const CONTROL_PLANE_DIR = path.join(REPOSITORY_ROOT, "_CONTROL_PLANE");
export const MASTER_MANIFEST_PATH = path.join(CONTROL_PLANE_DIR, "MASTER_MANIFEST.json");

export const RAW_ARCHIVE_DIR = path.join(REPOSITORY_ROOT, "_RAW_ARCHIVE");
export const CCR_CHECKPOINT_DIR = path.join(RAW_ARCHIVE_DIR, "ccr");
export const CHECKPOINT_PATH = path.join(CCR_CHECKPOINT_DIR, "ccr_bulk_checkpoint.json");
export const DOWNLOAD_CHECKPOINT_PATH = path.join(CCR_CHECKPOINT_DIR, "download_checkpoint.json");
export const CHECKPOINT_PATHS = [CHECKPOINT_PATH, DOWNLOAD_CHECKPOINT_PATH] as const;

export const STRUCTURED_OUTPUT_DIR = path.join(REPOSITORY_ROOT, "data", "structured_output");
export const PARSED_OUTPUT_DIR = STRUCTURED_OUTPUT_DIR;
export const PARSED_BILLS_DIR = path.join(STRUCTURED_OUTPUT_DIR, "bills");
export const PARSED_INDICES_DIR = path.join(STRUCTURED_OUTPUT_DIR, "indices");

export const GEODE_READ_INDEX_PATH = path.join(
  GEODE_WEB_ROOT,
  "data",
  "structured_output",
  "commons.sqlite3",
);
