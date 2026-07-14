"""Compare Geode prompt results with Colorado Rulemaking Search results."""

from __future__ import annotations

import argparse
import html
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from geode.utils.file_io import atomic_write_json, atomic_write_jsonl, atomic_write_text
from geode.search.query_index import QueryResult, query_index

RULEMAKING_APP_URL = "https://oit-rules-search-ui.coawsprod.com/"
REPORT_PATH = Path("docs/audits/RULEMAKING_SEARCH_PROMPT_COMPARISON_2026-07-08.md")
OUTPUT_DIR = Path("04_Rulemaking/_verification")
DETAIL_NAME = "rulemaking_search_prompt_comparison.jsonl"
SUMMARY_NAME = "rulemaking_search_prompt_comparison_summary.json"
API_VAR_RE = re.compile(
    r"""const\s+(?P<name>apiURL|lolKey)\s*=\s*["'](?P<value>[^"']+)["']""",
    re.IGNORECASE,
)


class OfficialSearchResult(BaseModel):
    """One official Colorado Rulemaking Search result used for comparison."""

    model_config = ConfigDict(extra="forbid")

    ccr_citation: str | None = None
    title: str | None = None
    agency: str | None = None
    department: str | None = None
    filing_type: str | None = None
    effective_date: str | None = None
    source_url: str | None = None
    has_rule_history: bool = False
    has_draft_rules: bool = False
    has_newer_version_warning: bool = False
    is_repealed: bool = False


class PromptComparisonRecord(BaseModel):
    """One prompt comparison row."""

    model_config = ConfigDict(extra="forbid")

    entity_type: str = "rulemaking_prompt_comparison"
    prompt_number: int
    prompt: str
    geode_result_count: int = Field(ge=0)
    official_result_count: int = Field(ge=0)
    geode_top_citations: list[str] = Field(default_factory=list)
    official_top_citations: list[str] = Field(default_factory=list)
    shared_citations: list[str] = Field(default_factory=list)
    geode_domains: list[str] = Field(default_factory=list)
    official_status_flags: list[str] = Field(default_factory=list)
    performance_status: str = Field(min_length=1)
    issue: str | None = None
    recommendation: str
    geode_top_results: list[dict[str, Any]] = Field(default_factory=list)
    official_top_results: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime


class PromptComparisonSummary(BaseModel):
    """Summary of the 50-prompt comparison run."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    prompt_count: int = Field(ge=0)
    geode_empty_results: int = Field(ge=0)
    official_empty_results: int = Field(ge=0)
    direct_overlap_prompts: int = Field(ge=0)
    partial_overlap_prompts: int = Field(ge=0)
    geode_broader_than_official: int = Field(ge=0)
    official_unavailable_prompts: int = Field(ge=0)
    needs_review_prompts: int = Field(ge=0)
    status_counts: dict[str, int]
    detail_path: str
    summary_path: str
    report_path: str
    boundary: str


def run_prompt_comparison(
    root: Path,
    prompt_file: Path,
    database_path: Path,
    live_official: bool = True,
    limit: int = 8,
    output_label: str | None = None,
    official_timeout: float = 12.0,
) -> PromptComparisonSummary:
    """Run the prompt comparison and write report outputs."""

    project_root = root.resolve()
    generated_at = datetime.now(timezone.utc)
    prompts = _read_prompts(prompt_file)
    try:
        official_client = _OfficialRulemakingClient(timeout=official_timeout) if live_official else None
    except (httpx.HTTPError, RuntimeError):
        official_client = None
    records: list[PromptComparisonRecord] = []

    for index, prompt in enumerate(prompts, start=1):
        geode_results = query_index(database_path, prompt, limit=limit)
        official_attempted = official_client is not None
        try:
            official_results = (
                official_client.search(prompt, result_count=25)
                if official_client
                else []
            )
        except (httpx.HTTPError, RuntimeError):
            official_results = []
            official_attempted = False
        records.append(
            _compare_prompt(
                prompt_number=index,
                prompt=prompt,
                geode_results=geode_results,
                official_results=official_results,
                official_attempted=official_attempted,
                generated_at=generated_at,
            )
        )
        if official_client:
            time.sleep(0.15)

    output_dir = project_root / OUTPUT_DIR
    detail_name, summary_name, report_path = _output_paths(output_label)
    detail_path = output_dir / detail_name
    summary_path = output_dir / summary_name
    report_path = project_root / report_path
    summary = _summary_for(records, generated_at, detail_path, summary_path, report_path)

    atomic_write_jsonl(detail_path, records, project_root)
    atomic_write_json(summary_path, summary, project_root)
    _write_markdown_report(report_path, summary, records, project_root)
    return summary


class _OfficialRulemakingClient:
    """Small client for the public Rulemaking Search API used by the state page."""

    def __init__(self, timeout: float = 12.0) -> None:
        self.timeout = timeout
        settings = self._load_public_settings()
        self.api_url = settings["apiURL"]
        self.api_key = settings["lolKey"]
        self.client = httpx.Client(timeout=timeout)

    def search(self, query: str, result_count: int) -> list[OfficialSearchResult]:
        """Run one official search."""

        response = self.client.post(
            self.api_url,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Origin": RULEMAKING_APP_URL.rstrip("/"),
                "Referer": RULEMAKING_APP_URL,
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
                "X-Api-Key": self.api_key,
            },
            json={
                "searchText": query,
                "olderRepealed": False,
                "resultCount": result_count,
            },
        )
        response.raise_for_status()
        payload = response.json()
        body = payload.get("body", payload)
        items = body.get("Items", body) if isinstance(body, dict) else body
        if isinstance(items, dict):
            items = list(items.values())
        if not isinstance(items, list):
            return []
        return [_official_result(item) for item in items if isinstance(item, dict)]

    def _load_public_settings(self) -> dict[str, str]:
        """Read API URL and public key from the official search page."""

        response = httpx.get(RULEMAKING_APP_URL, timeout=self.timeout)
        response.raise_for_status()
        settings = {match.group("name"): match.group("value") for match in API_VAR_RE.finditer(response.text)}
        missing = {"apiURL", "lolKey"} - set(settings)
        if missing:
            raise RuntimeError(f"official search page missing expected settings: {sorted(missing)}")
        return settings


def _compare_prompt(
    prompt_number: int,
    prompt: str,
    geode_results: list[QueryResult],
    official_results: list[OfficialSearchResult],
    official_attempted: bool,
    generated_at: datetime,
) -> PromptComparisonRecord:
    """Compare one Geode result set with one official result set."""

    geode_citations = _unique([result.citation for result in geode_results])
    official_citations = _unique([result.ccr_citation for result in official_results if result.ccr_citation])
    shared = _citation_overlap(geode_citations, official_citations)
    domains = _domains_for(geode_results)
    official_flags = _official_flags(official_results)
    status, issue, recommendation = _performance_status(
        geode_results=geode_results,
        official_results=official_results,
        official_attempted=official_attempted,
        shared=shared,
        geode_domains=domains,
    )

    return PromptComparisonRecord(
        prompt_number=prompt_number,
        prompt=prompt,
        geode_result_count=len(geode_results),
        official_result_count=len(official_results),
        geode_top_citations=geode_citations[:8],
        official_top_citations=official_citations[:8],
        shared_citations=shared,
        geode_domains=domains,
        official_status_flags=official_flags,
        performance_status=status,
        issue=issue,
        recommendation=recommendation,
        geode_top_results=[_geode_result_row(result) for result in geode_results[:5]],
        official_top_results=[result.model_dump(mode="json") for result in official_results[:5]],
        generated_at=generated_at,
    )


def _performance_status(
    geode_results: list[QueryResult],
    official_results: list[OfficialSearchResult],
    official_attempted: bool,
    shared: list[str],
    geode_domains: list[str],
) -> tuple[str, str | None, str]:
    """Assign a practical performance status."""

    if not official_attempted:
        return (
            "official_not_run",
            "Official Rulemaking Search was not queried.",
            "Run again with live official search enabled.",
        )
    if not geode_results and not official_results:
        return (
            "both_empty",
            "Neither system returned results.",
            "Add prompt-specific synonyms or ask with a citation, agency, or permit term.",
        )
    if not geode_results:
        return (
            "geode_empty",
            "Official search returned results but Geode did not.",
            "Add missing terms from official results to Geode routing and index tags.",
        )
    if not official_results:
        return (
            "geode_broader_than_official",
            "Geode returned source-backed results while the official CCR search returned none.",
            "Keep Geode behavior; note that the official tool is narrower and CCR-focused.",
        )
    if shared:
        return (
            "direct_overlap",
            None,
            "Good result. Keep this prompt in regression testing.",
        )
    if len(geode_domains) >= 3:
        return (
            "geode_broader_than_official",
            "Geode returned a broader compliance map than the official CCR search.",
            "Keep Geode's broader result, but surface the official CCR hits as current-status checks.",
        )
    return (
        "needs_review",
        "Both systems returned results, but the top citations did not overlap.",
        "Review whether Geode should boost the official CCR citations for this prompt type.",
    )


def _summary_for(
    records: list[PromptComparisonRecord],
    generated_at: datetime,
    detail_path: Path,
    summary_path: Path,
    report_path: Path,
) -> PromptComparisonSummary:
    """Build the summary record."""

    counts = Counter(record.performance_status for record in records)
    return PromptComparisonSummary(
        generated_at=generated_at,
        prompt_count=len(records),
        geode_empty_results=counts["geode_empty"],
        official_empty_results=sum(1 for record in records if record.official_result_count == 0),
        direct_overlap_prompts=counts["direct_overlap"],
        partial_overlap_prompts=counts["needs_review"],
        geode_broader_than_official=counts["geode_broader_than_official"],
        official_unavailable_prompts=counts["official_not_run"],
        needs_review_prompts=counts["needs_review"],
        status_counts=dict(sorted(counts.items())),
        detail_path=detail_path.as_posix(),
        summary_path=summary_path.as_posix(),
        report_path=report_path.as_posix(),
        boundary=(
            "This compares Geode's broad legal corpus search to Colorado's official "
            "Rulemaking Search, which is a narrower CCR/current-rule search. A lack "
            "of official overlap is not automatically a Geode failure."
        ),
    )


def _write_markdown_report(
    report_path: Path,
    summary: PromptComparisonSummary,
    records: list[PromptComparisonRecord],
    root: Path,
) -> None:
    """Write a human-readable audit report."""

    lines = [
        "# Geode vs Colorado Rulemaking Search Prompt Comparison",
        "",
        "Date: 2026-07-08",
        "",
        "## Summary",
        "",
        f"- Prompts tested: {summary.prompt_count}",
        f"- Geode empty results: {summary.geode_empty_results}",
        f"- Official empty results: {summary.official_empty_results}",
        f"- Direct citation overlap: {summary.direct_overlap_prompts}",
        f"- Geode broader than official search: {summary.geode_broader_than_official}",
        f"- Needs review: {summary.needs_review_prompts}",
        "",
        "## Boundary",
        "",
        summary.boundary,
        "",
        "## Overall Finding",
        "",
        _overall_finding(summary),
        "",
        "## Prompt Results",
        "",
    ]
    for record in records:
        issue = f" Issue: {record.issue}" if record.issue else ""
        lines.extend(
            [
                f"### {record.prompt_number}. {record.performance_status}",
                "",
                record.prompt,
                "",
                f"- Geode top citations: {', '.join(record.geode_top_citations[:5]) or 'none'}",
                f"- Official top citations: {', '.join(record.official_top_citations[:5]) or 'none'}",
                f"- Shared citations: {', '.join(record.shared_citations) or 'none'}",
                f"- Geode domains: {', '.join(record.geode_domains) or 'none'}",
                f"- Recommendation: {record.recommendation}{issue}",
                "",
            ]
        )
    atomic_write_text(report_path, "\n".join(lines), root)


def _overall_finding(summary: PromptComparisonSummary) -> str:
    """Return a concise human finding."""

    if summary.geode_empty_results == 0 and summary.needs_review_prompts == 0:
        return (
            "Geode performed well across the prompt set. The main difference is that "
            "Geode returns a broader compliance map, while the official search is narrower "
            "and focused on CCR current-rule records."
        )
    if summary.geode_empty_results == 0:
        return (
            "Geode returned results for every prompt. Some prompts need review because "
            "the official search surfaced different CCR citations than Geode's top results."
        )
    return (
        "Some prompts did not return Geode results and should be repaired before this prompt "
        "set becomes a release regression test."
    )


def _output_paths(output_label: str | None) -> tuple[str, str, Path]:
    """Return output filenames without overwriting prior prompt audits."""

    if not output_label:
        return DETAIL_NAME, SUMMARY_NAME, REPORT_PATH
    safe_label = re.sub(r"[^a-zA-Z0-9_-]+", "_", output_label).strip("_").lower()
    if not safe_label:
        return DETAIL_NAME, SUMMARY_NAME, REPORT_PATH
    return (
        f"rulemaking_search_prompt_comparison_{safe_label}.jsonl",
        f"rulemaking_search_prompt_comparison_summary_{safe_label}.json",
        Path(f"docs/audits/RULEMAKING_SEARCH_PROMPT_COMPARISON_{safe_label.upper()}.md"),
    )


def _official_result(item: dict[str, Any]) -> OfficialSearchResult:
    """Normalize one official search result."""

    simple_name = _clean(item.get("doc_simple_name"))
    current_version = _clean(item.get("doc_version"))
    additional_versions = item.get("doc_additional_versions")
    newest_version = None
    if isinstance(additional_versions, list) and additional_versions:
        newest_version = _clean(additional_versions[0].get("doc_version")) if isinstance(additional_versions[0], dict) else None

    return OfficialSearchResult(
        ccr_citation=_clean(item.get("doc_CCR")),
        title=html.unescape(simple_name or ""),
        agency=_clean(item.get("doc_agency")),
        department=_clean(item.get("doc_dept")),
        filing_type=_clean(item.get("doc_filing_type")),
        effective_date=_clean(item.get("doc_effective_date")),
        source_url=_clean(item.get("doc_uri")),
        has_rule_history=bool(additional_versions),
        has_draft_rules=bool(item.get("doc_draft_rules")),
        has_newer_version_warning=bool(current_version and newest_version and current_version != newest_version),
        is_repealed="repealed" in (simple_name or "").casefold(),
    )


def _geode_result_row(result: QueryResult) -> dict[str, Any]:
    """Return report-safe Geode result fields."""

    return {
        "id": result.id,
        "citation": result.citation,
        "title": result.title,
        "layer": result.layer,
        "entity_type": result.entityType,
        "score": result.score,
        "match_reasons": list(result.matchReasons),
        "source_url": result.sourceUrl,
    }


def _read_prompts(path: Path) -> list[str]:
    """Read prompts separated by blank lines."""

    text = path.read_text(encoding="utf-8")
    prompts = [prompt.strip() for prompt in re.split(r"\n\s*\n", text) if prompt.strip()]
    return [
        prompt
        for prompt in prompts
        if not prompt.lower().startswith("provide your feedback")
        and not _looks_like_prompt_file_heading(prompt)
    ]


def _looks_like_prompt_file_heading(prompt: str) -> bool:
    """Return true for attachment headings that are not search prompts."""

    normalized = prompt.strip().casefold()
    if len(normalized) > 120:
        return False
    return normalized.endswith("prompts") or normalized.endswith("search prompts")


def _citation_overlap(geode_citations: list[str], official_citations: list[str]) -> list[str]:
    """Return citations that match in either exact or canonical form."""

    official_by_key = {_citation_key(citation): citation for citation in official_citations}
    shared: list[str] = []
    for citation in geode_citations:
        key = _citation_key(citation)
        if key and key in official_by_key:
            shared.append(citation)
    return _unique(shared)


def _domains_for(results: list[QueryResult]) -> list[str]:
    """Infer high-level domains from Geode citations."""

    domains: list[str] = []
    for result in results:
        value = f"{result.id} {result.citation} {result.title} {result.layer}".casefold()
        if "5 ccr 1001" in value or "5_ccr_1001" in value or "crs-25-7" in value:
            domains.append("Air")
        if "5 ccr 1002" in value or "5_ccr_1002" in value or "crs-25-8" in value:
            domains.append("Water")
        if "6 ccr 1007" in value or "6_ccr_1007" in value or "crs-25-15" in value:
            domains.append("Waste")
        if "7 ccr 1103" in value or "7_ccr_1103" in value or "crs-8-" in value:
            domains.append("Labor")
        if (
            "29 cfr" in value
            or "29 u.s.c" in value
            or "29 usc" in value
            or "29 u s c" in value
            or "8 ccr 1507" in value
            or "8_ccr_1507" in value
            or "safety" in value
            or "injury" in value
            or "exposure" in value
        ):
            domains.append("Safety")
        if "rulemaking" in value or "04_rulemaking" in value:
            domains.append("Rulemaking")
    return _unique(domains)


def _official_flags(results: list[OfficialSearchResult]) -> list[str]:
    """Collect official current-status flags from result rows."""

    flags: list[str] = []
    for result in results:
        if result.has_newer_version_warning:
            flags.append("newer_version_available")
        if result.has_draft_rules:
            flags.append("proposed_rule_change")
        if result.is_repealed:
            flags.append("repealed")
        if result.has_rule_history:
            flags.append("rule_history_available")
    return _unique(flags)


def _citation_key(value: str | None) -> str:
    """Normalize CCR citation text for overlap checks."""

    if not value:
        return ""
    match = re.search(r"\b(\d{1,2})\s+CCR\s+(\d+)-(\d+(?:-\d+)?)\b", value, re.IGNORECASE)
    if match:
        return f"{match.group(1)}_CCR_{match.group(2)}-{match.group(3)}".casefold()
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _unique(values: list[str | None]) -> list[str]:
    """Return unique non-empty strings in order."""

    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean(value)
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _clean(value: object) -> str | None:
    """Return normalized text."""

    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def main(argv: list[str] | None = None) -> int:
    """Run the prompt comparison."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--no-live-official", action="store_true")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--label", help="Optional output label for a separate audit run.")
    parser.add_argument("--official-timeout", type=float, default=12.0)
    args = parser.parse_args(argv)
    summary = run_prompt_comparison(
        root=args.root,
        prompt_file=args.prompt_file,
        database_path=args.database,
        live_official=not args.no_live_official,
        limit=args.limit,
        output_label=args.label,
        official_timeout=args.official_timeout,
    )
    print(summary.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
