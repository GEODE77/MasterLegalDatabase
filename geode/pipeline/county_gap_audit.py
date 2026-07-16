"""Document official-source gaps for unresolved county authority categories."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from geode.schemas import CountyGapRecord
from geode.utils.file_io import atomic_write_jsonl, iter_jsonl, load_json


def build_gap_audit(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Create evidence-linked gap records and update unresolved matrix cells.

    A gap record does not claim that no law exists. It records that Geode's
    official-source discovery pass has not located a category-specific source,
    and preserves the county's official discovery URL and access result.
    """

    matrix_path = root / "_CONTROL_PLANE" / "COUNTY_SOURCE_COVERAGE.json"
    registry_path = root / "_CONTROL_PLANE" / "LOCAL_SOURCE_REGISTRY.json"
    matrix = load_json(matrix_path)
    registry = load_json(registry_path)
    homepage_by_authority = {
        str(row["authority_id"]): row
        for row in registry.get("pilot", {}).get("counties", [])
    }
    audited_at = datetime.now(timezone.utc)
    manifest_rows = list(iter_jsonl(root / "_CONTROL_PLANE" / "LOCAL_DOWNLOAD_MANIFEST.jsonl"))
    attempts_by_source: dict[str, list[dict[str, Any]]] = {}
    for row in manifest_rows:
        attempts_by_source.setdefault(str(row.get("source_id")), []).append(row)
    homepage_rows = {
        str(row.get("authority_id")): row
        for row in manifest_rows
        if row.get("authority_level") == "county"
        and row.get("requested_url") == row.get("source_url")
    }
    candidates_by_cell: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for source in registry.get("pilot", {}).get("county_sources", []):
        candidates_by_cell.setdefault(
            (str(source.get("authority_id")), str(source.get("category"))), []
        ).append(source)
    records: list[dict[str, Any]] = []

    for county in matrix.get("counties", []):
        authority_id = str(county["county_id"])
        homepage = homepage_by_authority.get(authority_id, {})
        homepage_state = county.get("homepage", {})
        homepage_url = str(homepage.get("url", ""))
        homepage_row = homepage_rows.get(authority_id, {})
        homepage_status = str(homepage_state.get("status", "not_attempted"))
        for category, cell in county.get("source_categories", {}).items():
            if cell.get("status") not in {"not_started", "blocked", "source_identified"}:
                continue
            candidates = candidates_by_cell.get((authority_id, category), [])
            candidate_ids = [str(source["source_id"]) for source in candidates]
            attempts = [
                attempt
                for source_id in candidate_ids
                for attempt in attempts_by_source.get(source_id, [])
            ]
            successful = [attempt for attempt in attempts if attempt.get("status") == "downloaded"]
            if successful:
                cell["status"] = "downloaded"
                cell["source_ids"] = sorted(set(cell.get("source_ids", [])) | {
                    str(attempt["source_id"]) for attempt in successful
                })
                cell["notes"] = "Official source preserved; normalization and category review remain pending."
                continue
            if homepage_status == "downloaded":
                if candidates and not attempts:
                    disposition = "source_identified_not_attempted"
                    reason = "A category-specific official source is registered but has not yet been attempted."
                elif attempts:
                    disposition = "download_failed"
                    reason = "A category-specific official source was attempted but no download succeeded."
                else:
                    disposition = "official_source_not_identified"
                    reason = "The official county discovery page was reviewed, but no category-specific source is registered."
            elif homepage_status == "blocked":
                disposition = "download_failed" if attempts else "official_discovery_page_access_blocked"
                reason = (
                    "A category-specific source was attempted but did not download."
                    if attempts
                    else "The official county discovery page was registered but could not be downloaded."
                )
            else:
                disposition = "official_discovery_page_access_blocked"
                reason = "No official county discovery download result is recorded."
            if disposition == "source_identified_not_attempted":
                cell["status"] = "source_identified"
            else:
                cell["status"] = "blocked"
            cell["notes"] = (
                f"Disposition: {disposition}; see COUNTY_GAP_AUDIT.jsonl. "
                f"Discovery URL: {homepage_url or 'not recorded'}"
            )
            record = CountyGapRecord(
                gap_id=f"GAP-{authority_id}-{category}",
                authority_id=authority_id,
                county_name=str(county.get("county_name")),
                category=category,
                disposition=disposition,
                official_discovery_url=homepage_url or None,
                official_discovery_status=homepage_status,
                official_discovery_raw_path=homepage_state.get("raw_path"),
                official_discovery_sha256=homepage_row.get("sha256") or None,
                candidate_source_ids=candidate_ids,
                attempted_source_ids=sorted({str(attempt["source_id"]) for attempt in attempts}),
                failed_source_ids=sorted({
                    str(attempt["source_id"])
                    for attempt in attempts
                    if attempt.get("status") == "failed"
                }),
                evidence_message="; ".join(
                    str(attempt.get("message", "")) for attempt in attempts if attempt.get("message")
                ) or str(homepage_state.get("message", "")),
                reason=reason,
                audited_at=audited_at,
            )
            records.append(record.model_dump(mode="json"))

        statuses = [entry.get("status") for entry in county.get("source_categories", {}).values()]
        county["overall_status"] = "blocked" if statuses and all(status == "blocked" for status in statuses) else "partial"

    return records, matrix


def run_gap_audit(root: Path) -> Path:
    """Write the gap audit and updated county coverage matrix."""

    from geode.utils.file_io import atomic_write_json

    records, matrix = build_gap_audit(root)
    audit_path = root / "_CONTROL_PLANE" / "COUNTY_GAP_AUDIT.jsonl"
    matrix_path = root / "_CONTROL_PLANE" / "COUNTY_SOURCE_COVERAGE.json"
    manifest_path = root / "_CONTROL_PLANE" / "MASTER_MANIFEST.json"
    atomic_write_jsonl(audit_path, records, root)
    atomic_write_json(matrix_path, matrix, root)
    if manifest_path.exists():
        manifest = load_json(manifest_path)
        for layer in manifest.get("data_layers", []):
            if layer.get("id") != "08_County_Authorities":
                continue
            layer["known_gaps"] = (
                [
                    f"{len(records)} county source-category gaps remain in the latest audit."
                ]
                if records
                else [
                    "Official county source-category gap audit is clear; semantic "
                    "normalization and review queues remain open."
                ]
            )
            layer["last_checked"] = datetime.now(timezone.utc).date().isoformat()
            layer["status"] = "ready"
            break
        atomic_write_json(manifest_path, manifest, root)
    return audit_path


def main() -> None:
    """Run the county official-source gap audit from the command line."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    path = run_gap_audit(args.root.resolve())
    print(path)


if __name__ == "__main__":
    main()
