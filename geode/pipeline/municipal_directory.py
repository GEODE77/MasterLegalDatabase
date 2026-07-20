"""Materialize the statewide municipality expansion queue from the CML directory."""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from geode.utils.file_io import atomic_write_json, load_json


CML_SOURCE_ID = "municipal_statewide_cml_directory"
CML_RAW_PATH = Path("_RAW_ARCHIVE/local/municipal") / CML_SOURCE_ID / "landing_page.html"
OUTPUT_PATH = Path("_CONTROL_PLANE") / "MUNICIPAL_EXPANSION_QUEUE.json"
EXCLUDED_NON_MUNICIPAL_ENTRIES = {"Sheriden Lake"}


def materialize_municipal_expansion_queue(root: Path) -> dict[str, int]:
    """Create a named queue for municipalities listed by the official CML page."""

    resolved_root = root.resolve()
    source_path = resolved_root / CML_RAW_PATH
    text = source_path.read_text(encoding="utf-8", errors="replace")
    start_marker = "Links to Colorado cities and towns"
    end_marker = "Updated May 6, 2024"
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        raise ValueError("CML municipality link table was not found in the archived page")
    table = text[start:end]
    entries: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for item in re.findall(r"<li>(.*?)</li>", table, flags=re.IGNORECASE | re.DOTALL):
        name = re.sub(r"<[^>]+>", " ", item)
        name = html.unescape(re.sub(r"\s+", " ", name)).strip()
        name = re.sub(r"\s*\*\s*$", "", name).strip()
        if not name or name in seen or name in EXCLUDED_NON_MUNICIPAL_ENTRIES:
            continue
        seen.add(name)
        href_match = re.search(r"href=[\"']([^\"']+)[\"']", item, flags=re.IGNORECASE)
        website = urljoin("https://www.cml.org/", html.unescape(href_match.group(1))) if href_match else None
        entries.append({"name": name, "cml_website": website, "status": "not_registered"})

    registry_path = resolved_root / "_CONTROL_PLANE" / "MUNICIPAL_SOURCE_REGISTRY.json"
    registry = load_json(registry_path)
    registered = {
        _canonical_name(str(entry["name"])): str(entry["authority_id"])
        for entry in registry.get("pilot", {}).get("municipalities", [])
    }
    for entry in entries:
        authority_id = registered.get(_canonical_name(str(entry["name"])))
        if authority_id:
            entry["status"] = "registered"
            entry["authority_id"] = authority_id

    registered_count = sum(entry["status"] == "registered" for entry in entries)
    payload = {
        "schema_version": 1,
        "state": "CO",
        "authority_level": "municipal",
        "source_id": CML_SOURCE_ID,
        "source_url": "https://www.cml.org/home/networking-events/membership/membership",
        "source_path": CML_RAW_PATH.as_posix(),
        "source_retrieved_at": datetime.now(timezone.utc).isoformat(),
        "incorporated_municipality_target": 273,
        "directory_entries": len(entries),
        "registered_entries": registered_count,
        "not_registered_entries": len(entries) - registered_count,
        "excluded_non_municipal_entries": sorted(EXCLUDED_NON_MUNICIPAL_ENTRIES),
        "entries": entries,
    }
    atomic_write_json(resolved_root / OUTPUT_PATH, payload, resolved_root)
    return {
        "directory_entries": len(entries),
        "registered": sum(entry["status"] == "registered" for entry in entries),
        "not_registered": sum(entry["status"] == "not_registered" for entry in entries),
    }


def _canonical_name(value: str) -> str:
    """Normalize CML names against Geode's descriptive authority names."""

    normalized = re.sub(r"\s+", " ", value).strip().casefold()
    normalized = re.sub(r"^(city and county|city|town)\s+of\s+", "", normalized)
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


if __name__ == "__main__":
    print(json.dumps(materialize_municipal_expansion_queue(Path.cwd()), indent=2))
