"""Live CCR ingestion orchestration."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from geode.connectors.ccr_scraper import CCRRuleEntry, download_rule, resolve_rule_info_page
from geode.extractors.converter import (
    ConversionResult,
    convert_to_markdown,
)
from geode.net.http_client import build_session
from geode.pipeline.writer import ensure_project_structure
from geode.scoring.industry_tagger import load_taxonomies, tag_bill

LOGGER = logging.getLogger(__name__)

_CCR_RULE_URL = "https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId="
_CRS_CITATION_PATTERN = re.compile(
    r"(?:\bsection\s+|\u00a7\s*)?"
    r"\d{1,2}(?:\.\d+)?-\d{1,3}(?:\.\d+)?-\d{1,4}(?:\.\d+)?"
    r"(?:\s*\([^)]+\))*"
    r"(?:\s*,?\s*(?:C\.?\s*R\.?\s*S\.?|Colorado\s+Revised\s+Statutes))?",
    re.IGNORECASE,
)


def run_ccr_pipeline(
    root: Path,
    rule_id: str,
    *,
    output_dir: str = "data",
    taxonomy_dir: str = "taxonomies",
    dry_run: bool = False,
    fmt: str = "markdown",
) -> int:
    """Fetch a CCR rule by rule_id, convert, tag, and persist outputs.

    Args:
        root: Project root.
        rule_id: Secretary of State CCR rule identifier.
        output_dir: Base output directory for raw, normalized, and tagged data.
        taxonomy_dir: Directory containing deterministic taxonomy files.
        dry_run: Log planned operations without network activity or disk writes.
        fmt: Normalized output format: ``markdown``, ``json``, or ``both``.

    Returns:
        Process exit code: 0 on success, non-zero on failure.
    """

    try:
        root = root.resolve()
        source_url = _resolve_ccr_url(rule_id)
        paths = _output_paths(root, rule_id, output_dir)
        LOGGER.info("resolve: CCR rule %s -> %s", rule_id, source_url)

        if dry_run:
            LOGGER.info("fetch: would use one hardened HTTP session.")
            LOGGER.info("convert: would convert downloaded source to %s.", fmt)
            LOGGER.info("tag: would load taxonomies from %s.", root / taxonomy_dir)
            LOGGER.info(
                "write: raw=%s normalized=%s tagged=%s",
                paths["raw"],
                paths["normalized"],
                paths["tagged"],
            )
            return 0

        _validate_format(fmt)
        ensure_project_structure(root)
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)

        LOGGER.info("fetch: resolving downloadable CCR source for %s", source_url)
        session = build_session()
        try:
            resolved_entry = resolve_rule_info_page(
                CCRRuleEntry(
                    ccr_number=rule_id,
                    department="Unresolved Department",
                    agency="Unresolved Agency",
                    source_page_url=source_url,
                ),
                client=session,
            )
            raw_path = download_rule(resolved_entry, paths["raw"], client=session)
        finally:
            _close_session(session)

        LOGGER.info("convert: converting %s", raw_path)
        conversion = _convert_source(raw_path, resolved_entry.preferred_url)

        LOGGER.info("tag: tagging converted CCR text")
        taxonomy_path = _resolve_optional_root_path(root, taxonomy_dir)
        tag_record = tag_bill(_taggable_record(rule_id, conversion), load_taxonomies(str(taxonomy_path)))

        LOGGER.info("write: writing normalized and tagged outputs")
        _write_outputs(paths, rule_id, source_url, raw_path, conversion, tag_record, fmt)
    except Exception as exc:
        LOGGER.error("CCR pipeline failed for rule %s: %s", rule_id, exc, exc_info=True)
        return 1

    return 0


def _resolve_ccr_url(rule_id: str) -> str:
    """Resolve a Secretary of State rule id to the public rule-info URL."""

    normalized = rule_id.strip()
    if not normalized:
        raise ValueError("rule_id must not be empty")
    return f"{_CCR_RULE_URL}{normalized}"


def _output_paths(root: Path, rule_id: str, output_dir: str) -> dict[str, Path]:
    """Return canonical CCR output directories."""

    base = _resolve_optional_root_path(root, output_dir)
    return {
        "raw": base / "raw" / "Colorado" / "CCR",
        "normalized": base / "normalized" / "Colorado" / "CCR",
        "tagged": base / "tagged",
    }


def _resolve_optional_root_path(root: Path, value: str) -> Path:
    """Resolve an absolute or root-relative path value."""

    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def _validate_format(fmt: str) -> None:
    """Validate the requested normalized output format."""

    if fmt not in {"markdown", "json", "both"}:
        raise ValueError('fmt must be one of "markdown", "json", or "both"')


def _convert_source(source_path: Path, source_url: str) -> ConversionResult:
    """Convert a downloaded CCR source to Markdown."""

    return convert_to_markdown(source_path, source_url=source_url)


def _taggable_record(rule_id: str, conversion: ConversionResult) -> dict[str, Any]:
    """Build the minimal record shape accepted by the deterministic tagger."""

    markdown = conversion.markdown_text
    return {
        "bill_number": f"CCR-{rule_id}",
        "title": _first_title(markdown) or f"CCR-{rule_id}",
        "crs_references": _extract_crs_references(markdown),
        "committees": [],
    }


def _first_title(markdown: str) -> str:
    """Return the first non-empty heading or line from converted text."""

    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        return stripped.lstrip("#").strip()
    return ""


def _extract_crs_references(markdown: str) -> list[str]:
    """Extract CRS references from converted CCR text for deterministic tagging."""

    seen: set[str] = set()
    references: list[str] = []
    for match in _CRS_CITATION_PATTERN.finditer(markdown):
        citation = match.group(0).strip()
        if citation and citation not in seen:
            seen.add(citation)
            references.append(citation)
    return references


def _write_outputs(
    paths: dict[str, Path],
    rule_id: str,
    source_url: str,
    raw_path: Path,
    conversion: ConversionResult,
    tag_record: dict[str, Any],
    fmt: str,
) -> None:
    """Write normalized and tagged CCR artifacts."""

    stem = f"ccr_rule_{_safe_stem(rule_id)}"
    metadata = {
        "id": f"CCR-{rule_id}",
        "entity_type": "regulation_rule",
        "source_url": source_url,
        "raw_path": raw_path.as_posix(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "conversion": conversion.model_dump(mode="json", exclude={"markdown_text"}),
    }

    if fmt in {"markdown", "both"}:
        _atomic_write_text(
            paths["normalized"] / f"{stem}.md",
            _render_markdown(metadata, conversion.markdown_text),
        )
    if fmt in {"json", "both"}:
        _atomic_write_json(
            paths["normalized"] / f"{stem}.json",
            {**metadata, "markdown_text": conversion.markdown_text},
        )
    _atomic_write_json(paths["tagged"] / f"{stem}_tags.json", tag_record)


def _render_markdown(metadata: dict[str, Any], markdown_text: str) -> str:
    """Render normalized CCR Markdown with YAML frontmatter."""

    lines = [
        "---",
        f'id: "{metadata["id"]}"',
        f'entity_type: "{metadata["entity_type"]}"',
        f'source_url: "{metadata["source_url"]}"',
        f'raw_path: "{metadata["raw_path"]}"',
        f'generated_at: "{metadata["generated_at"]}"',
        "---",
        "",
        markdown_text.rstrip(),
        "",
    ]
    return "\n".join(lines)


def _atomic_write_text(path: Path, text: str) -> None:
    """Write text atomically."""

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    try:
        tmp_path.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically."""

    _atomic_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def _safe_stem(value: str) -> str:
    """Return a filesystem-safe stem."""

    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_") or "rule"


def _close_session(session: Any) -> None:
    """Close a session when it exposes a close method."""

    close = getattr(session, "close", None)
    if callable(close):
        close()
