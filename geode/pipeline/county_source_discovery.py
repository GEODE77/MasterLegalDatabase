"""Discover additional county legal-source links from already archived official pages."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from geode.constants import AUTHORIZED_SOURCE_HOSTS
from geode.utils.file_io import atomic_write_json, iter_jsonl, load_json

CONTROL = Path("_CONTROL_PLANE")
CATEGORY_TERMS: dict[str, tuple[str, ...]] = {
    "county_ordinances": ("ordinance", "ordinances", "county-code", "county_code"),
    "county_codes": ("county-code", "county_code", "code", "codes"),
    "land_use_zoning": ("zoning", "land-use", "land_use", "planning", "development"),
    "subdivision_development": ("subdivision", "land-division", "development"),
    "building_construction": ("building", "construction", "building-code"),
    "public_health": ("public-health", "health", "septic", "wastewater"),
    "environmental_open_burning": ("open-burning", "open_burning", "burning", "air-quality"),
    "roads_transportation_access": ("road", "roads", "transportation", "right-of-way"),
    "animal_control_nuisance": ("animal", "nuisance", "dog-control"),
    "emergency_fire_restrictions": ("fire", "emergency", "fire-ban", "fire_restriction"),
    "continuing_resolutions": ("resolution", "resolutions", "commissioners"),
    "administrative_rule_manuals": ("regulation", "regulations", "policy", "manual"),
    "archived_versions": ("archive", "archived", "historical", "prior-version"),
}


def discover_county_sources(root: Path, *, write: bool = False) -> dict[str, object]:
    """Find category-specific official links in downloaded county HTML pages.

    Discovered links are marked as candidates in the registry. The function
    does not claim that a link contains a law until the downloader and normal
    ingestion pipeline successfully process it.
    """

    resolved = root.resolve()
    registry = load_json(resolved / CONTROL / "LOCAL_SOURCE_REGISTRY.json")
    pilot = registry.setdefault("pilot", {})
    sources = list(pilot.get("county_sources", []))
    existing_pairs = {
        (str(row.get("authority_id")), str(row.get("category")), str(row.get("url")))
        for row in sources
    }
    existing_cells = {
        (str(row.get("authority_id")), str(row.get("category"))) for row in sources
    }
    county_ids = {
        str(row.get("authority_id")) for row in pilot.get("counties", [])
    }
    manifest_path = resolved / CONTROL / "LOCAL_DOWNLOAD_MANIFEST.jsonl"
    candidates: list[dict[str, str]] = []
    for row in iter_jsonl(manifest_path):
        if row.get("status") != "downloaded" or row.get("authority_level") != "county":
            continue
        authority_id = str(row.get("authority_id"))
        if authority_id not in county_ids:
            continue
        raw_path = Path(str(row.get("raw_path", "")))
        if not raw_path.exists() or raw_path.suffix.casefold() not in {".html", ".htm"}:
            continue
        html = raw_path.read_text(encoding="utf-8", errors="ignore")
        for href, label in _links(html):
            url = urljoin(str(row.get("requested_url")), href).split("#", 1)[0]
            if not _approved(url):
                continue
            searchable = f"{url} {label}".casefold()
            for category, terms in CATEGORY_TERMS.items():
                cell = (authority_id, category)
                if (
                    cell in existing_cells
                    or (authority_id, category, url) in existing_pairs
                    or not any(term in searchable for term in terms)
                ):
                    continue
                source_id = _source_id(authority_id, category, url)
                candidate = {
                    "source_id": source_id,
                    "authority_id": authority_id,
                    "authority_level": "county",
                    "category": category,
                    "url": url,
                    "discovery_method": "archived_official_page_link",
                    "discovery_parent_url": str(row.get("requested_url")),
                    "known_gaps": ["Candidate source requires download and Geode review."],
                }
                candidates.append(candidate)
                existing_pairs.add((authority_id, category, url))
                existing_cells.add(cell)
    if write and candidates:
        pilot["county_sources"] = [*sources, *candidates]
        atomic_write_json(resolved / CONTROL / "LOCAL_SOURCE_REGISTRY.json", registry, resolved)
    return {
        "candidates": len(candidates),
        "written": bool(write and candidates),
        "source_ids": [row["source_id"] for row in candidates],
    }


def _links(html: str) -> list[tuple[str, str]]:
    """Extract href and nearby visible label from simple government HTML."""

    matches = re.findall(
        r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return [(href.strip(), re.sub(r"<[^>]+>", " ", label).strip()) for href, label in matches]


def _approved(url: str) -> bool:
    """Return whether a discovered URL belongs to an approved official host."""

    parsed = urlparse(url)
    host = parsed.netloc.casefold()
    return parsed.scheme == "https" and (
        host in AUTHORIZED_SOURCE_HOSTS or host.endswith(".colorado.gov")
    )


def _source_id(authority_id: str, category: str, url: str) -> str:
    """Create a stable identifier for a discovered candidate URL."""

    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    slug = re.sub(r"[^a-z0-9]+", "_", category.casefold()).strip("_")
    return f"county_{authority_id.removeprefix('CO-COUNTY-').casefold()}_{slug}_{digest}"


def main() -> int:
    """Run the county source discovery command."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    print(discover_county_sources(args.root, write=args.write))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
