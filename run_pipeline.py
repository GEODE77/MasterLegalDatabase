"""Run the deterministic Project Geode bill pipeline.

The pipeline is sample-first by design. Live scraping is available as an
explicit opt-in Stage 0, while the normal test path starts from generated sample
extracted JSON or already-downloaded PDFs. No stage makes LLM API calls.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

TOTAL_STAGES = 7
DEFAULT_OUTPUT_DIR = "data"
DEFAULT_FINAL_FORMAT = "markdown"
DEFAULT_TAXONOMY_DIR = "taxonomies"

LOGGER = logging.getLogger("geode.pipeline")


@dataclass(frozen=True)
class PipelinePaths:
    """Resolved directories used by the pipeline."""

    base: Path
    raw_pdfs: Path
    extracted_text: Path
    structured_output: Path
    bills: Path
    indices: Path
    log_file: Path


@dataclass
class StageResult:
    """Execution metadata for one pipeline stage."""

    number: int
    name: str
    status: str
    duration_seconds: float = 0.0
    summary: Any = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class StageDefinition:
    """Static definition for a pipeline stage."""

    number: int
    name: str
    action: Callable[[], Any]


def build_paths(output_dir: str) -> PipelinePaths:
    """Build canonical pipeline paths from a base output directory.

    Args:
        output_dir: Base data directory supplied by the CLI.

    Returns:
        Resolved path bundle for all pipeline stages.
    """
    base = Path(output_dir)
    structured_output = base / "structured_output"
    return PipelinePaths(
        base=base,
        raw_pdfs=base / "raw_pdfs",
        extracted_text=base / "extracted_text",
        structured_output=structured_output,
        bills=structured_output / "bills",
        indices=structured_output / "indices",
        log_file=base / "pipeline_run.log",
    )


def configure_logging(paths: PipelinePaths, verbose: bool, dry_run: bool) -> None:
    """Configure logging to stdout and, when executing, a run log file.

    Args:
        paths: Pipeline path bundle.
        verbose: Whether to emit DEBUG-level logging.
        dry_run: Whether the pipeline is only describing planned work.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    level = logging.DEBUG if verbose else logging.INFO
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(console_handler)

    if not dry_run:
        paths.base.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(paths.log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        root_logger.addHandler(file_handler)


def validate_stage_range(start_stage: int, end_stage: int) -> None:
    """Validate requested start and end stage numbers.

    Args:
        start_stage: First numbered stage to run.
        end_stage: Last numbered stage to run.

    Raises:
        ValueError: If the range is outside 1 through 7 or inverted.
    """
    if not 1 <= start_stage <= TOTAL_STAGES:
        raise ValueError(f"--start-stage must be between 1 and {TOTAL_STAGES}.")
    if not 1 <= end_stage <= TOTAL_STAGES:
        raise ValueError(f"--end-stage must be between 1 and {TOTAL_STAGES}.")
    if start_stage > end_stage:
        raise ValueError("--start-stage cannot be greater than --end-stage.")


def validate_start_stage_inputs(
    start_stage: int,
    paths: PipelinePaths,
    sample: bool,
    scrape: bool,
) -> None:
    """Ensure the first requested stage has the files it needs.

    Args:
        start_stage: First numbered stage that will execute.
        paths: Pipeline path bundle.
        sample: Whether sample data mode is active.
        scrape: Whether live scraping is requested before Stage 1.

    Raises:
        FileNotFoundError: If the required directory or files are missing.
    """
    if sample and start_stage <= 2:
        requirement = (
            paths.extracted_text,
            "*_extracted.json",
            "Run scripts/generate_sample_data.py, then retry --sample.",
        )
    else:
        requirement = _stage_input_requirement(start_stage, paths, scrape)

    if requirement is None:
        return

    directory, pattern, suggestion = requirement
    if not directory.exists():
        raise FileNotFoundError(
            f"Stage {start_stage} requires {directory}, but it does not exist. "
            f"{suggestion}"
        )

    if not any(directory.glob(pattern)):
        raise FileNotFoundError(
            f"Stage {start_stage} requires files matching {directory / pattern}. "
            f"{suggestion}"
        )


def run_pipeline(
    session: str | None = None,
    start_stage: int | None = None,
    end_stage: int = TOTAL_STAGES,
    final_format: str = DEFAULT_FINAL_FORMAT,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    taxonomy_dir: str = DEFAULT_TAXONOMY_DIR,
    sample: bool = False,
    scrape: bool = False,
    dry_run: bool = False,
) -> list[StageResult]:
    """Run the configured pipeline stage range.

    Args:
        session: Colorado legislative session identifier, required for scraping.
        start_stage: First numbered stage to execute, or None for mode defaults.
        end_stage: Last numbered stage to execute.
        final_format: Output format for the formatter stage.
        output_dir: Base data directory.
        taxonomy_dir: Directory containing taxonomy files.
        sample: Whether to seed extracted sample data and skip extraction.
        scrape: Whether to run optional live scraping before numbered stages.
        dry_run: If true, only describe planned work.

    Returns:
        Stage results, including skipped stages.
    """
    if sample and scrape:
        raise ValueError("--sample and --scrape cannot be used together.")
    if scrape and not session:
        raise ValueError("--session is required when --scrape is used.")

    paths = build_paths(output_dir)
    missing_input_error: str | None = None
    try:
        effective_start_stage = resolve_start_stage(start_stage, paths, sample, scrape)
    except FileNotFoundError as exc:
        if not dry_run:
            raise
        effective_start_stage = 1
        missing_input_error = str(exc)

    validate_stage_range(effective_start_stage, end_stage)

    stages = build_stage_definitions(paths, final_format, taxonomy_dir)
    results: list[StageResult] = []
    pipeline_start = time.perf_counter()
    mode_used = resolve_mode_used(sample, scrape)
    data_mode = (
        "existing data (missing inputs)"
        if missing_input_error
        else describe_data_mode(sample, scrape, session, effective_start_stage)
    )

    log_mode_banner(sample, scrape, session)

    if dry_run:
        print_dry_run_plan(
            paths=paths,
            stages=stages,
            start_stage=effective_start_stage,
            end_stage=end_stage,
            final_format=final_format,
            taxonomy_dir=taxonomy_dir,
            sample=sample,
            scrape=scrape,
            session=session,
            data_mode=data_mode,
            mode_used=mode_used,
            input_error=missing_input_error,
        )
        results = build_dry_run_results(
            stages=stages,
            start_stage=effective_start_stage,
            end_stage=end_stage,
            sample=sample,
            scrape=scrape,
            input_error=missing_input_error,
        )
        total_seconds = time.perf_counter() - pipeline_start
        print_final_summary(
            results,
            paths,
            final_format,
            total_seconds,
            data_mode,
            mode_used,
            sample,
            dry_run=True,
        )
        return results

    if sample:
        sample_result = execute_sample_seed(paths, dry_run)
        results.append(sample_result)

    if scrape:
        scrape_stage = StageDefinition(0, "SCRAPE", lambda: _run_scrape_stage(session, paths))
        results.append(execute_stage(scrape_stage))

    validate_start_stage_inputs(effective_start_stage, paths, sample, scrape)

    try:
        for stage in stages:
            if stage.number < effective_start_stage or stage.number > end_stage:
                results.append(StageResult(stage.number, stage.name, "skipped"))
                continue

            results.append(execute_stage(stage))
    except KeyboardInterrupt as exc:
        interrupted_result = exc.args[0] if exc.args else None
        if isinstance(interrupted_result, StageResult):
            results.append(interrupted_result)
        total_seconds = time.perf_counter() - pipeline_start
        print_final_summary(
            results,
            paths,
            final_format,
            total_seconds,
            data_mode,
            mode_used,
            sample,
            dry_run=False,
        )
        raise

    total_seconds = time.perf_counter() - pipeline_start
    print_final_summary(
        results,
        paths,
        final_format,
        total_seconds,
        data_mode,
        mode_used,
        sample,
        dry_run=False,
    )
    return results


def resolve_start_stage(
    requested_start_stage: int | None,
    paths: PipelinePaths,
    sample: bool,
    scrape: bool,
) -> int:
    """Resolve the first numbered stage based on mode and existing inputs.

    Args:
        requested_start_stage: User-provided start stage, if any.
        paths: Pipeline path bundle.
        sample: Whether sample mode is active.
        scrape: Whether live scraping is active.

    Returns:
        Effective stage number to start from.

    Raises:
        FileNotFoundError: If no default input data exists for existing-data mode.
    """
    if requested_start_stage is not None:
        if sample and requested_start_stage < 2:
            return 2
        return requested_start_stage

    if sample:
        return 2
    if scrape:
        return 1
    if _has_files(paths.extracted_text, "*_extracted.json"):
        return 2
    if _has_files(paths.raw_pdfs, "*.pdf"):
        return 1

    raise FileNotFoundError(
        f"No input data found in {paths.extracted_text} or {paths.raw_pdfs}. "
        "Use --sample for generated test data or --scrape --session 2025a "
        "for live bill PDFs."
    )


def describe_data_mode(
    sample: bool,
    scrape: bool,
    session: str | None,
    start_stage: int,
) -> str:
    """Return a human-readable data mode label for summaries and plans."""
    if sample:
        return "sample data"
    if scrape:
        return f"live data ({session})"
    if start_stage == 1:
        return "existing PDF data"
    if start_stage == 2:
        return "existing extracted data"
    return "existing structured data"


def resolve_mode_used(sample: bool, scrape: bool) -> str:
    """Return the high-level mode label used in final summaries."""
    if sample:
        return "SAMPLE"
    if scrape:
        return "LIVE"
    return "RESUME"


def log_mode_banner(sample: bool, scrape: bool, session: str | None) -> None:
    """Print the selected high-level pipeline mode."""
    if sample:
        LOGGER.info("═══ SAMPLE MODE: Using generated test data (5 bills) ═══")
    elif scrape:
        LOGGER.info("═══ LIVE MODE: Downloading and processing session %s ═══", session)


def print_dry_run_plan(
    paths: PipelinePaths,
    stages: list[StageDefinition],
    start_stage: int,
    end_stage: int,
    final_format: str,
    taxonomy_dir: str,
    sample: bool,
    scrape: bool,
    session: str | None,
    data_mode: str,
    mode_used: str,
    input_error: str | None = None,
) -> None:
    """Print the full dry-run plan without importing or executing stages.

    Args:
        paths: Pipeline path bundle.
        stages: Numbered pipeline stages.
        start_stage: Effective first numbered stage.
        end_stage: Last numbered stage.
        final_format: Requested formatter output.
        taxonomy_dir: Taxonomy file directory.
        sample: Whether sample mode is active.
        scrape: Whether live scraping is active.
        session: Optional live session identifier.
        data_mode: Human-readable data mode.
        mode_used: SAMPLE, LIVE, or RESUME.
        input_error: Optional missing-input explanation.
    """
    LOGGER.info("═══ DRY RUN: PROJECT GEODE PIPELINE PLAN ═══")
    LOGGER.info("Mode: %s", data_mode)
    LOGGER.info("Mode used: %s", mode_used)
    LOGGER.info("Format: %s", final_format)
    if input_error:
        LOGGER.error("Input data check: ERROR: %s", input_error)
    LOGGER.info("")
    print_architecture(paths, taxonomy_dir)
    LOGGER.info("")
    LOGGER.info("Stages that would execute:")
    if input_error:
        LOGGER.info("- No stages would execute until input data exists.")
    elif scrape:
        LOGGER.info("- Stage 0 SCRAPE: would run for session %s", session)
    elif sample:
        LOGGER.info("- Sample data will be seeded automatically before Stage 2.")
        LOGGER.info("- SAMPLE SEED: would copy data/sample/ into %s", paths.extracted_text)

    for stage in stages:
        if input_error:
            status = "blocked; no input data found"
        elif sample and stage.number == 1:
            status = "skipped; sample data is already extracted"
        elif stage.number < start_stage or stage.number > end_stage:
            status = "skipped"
        else:
            status = "would execute"
        LOGGER.info("- Stage %s %s: %s", stage.number, stage.name, status)

    LOGGER.info("")
    LOGGER.info("Input directories that must exist:")
    for directory, pattern, reason in required_inputs_for_plan(
        start_stage,
        paths,
        sample,
        scrape,
    ):
        LOGGER.info("- %s (%s): %s", directory, pattern, reason)


def print_architecture(paths: PipelinePaths, taxonomy_dir: str) -> None:
    """Print the Project Geode two-layer data architecture tree.

    Args:
        paths: Pipeline path bundle.
        taxonomy_dir: Taxonomy file directory.
    """
    LOGGER.info("Data architecture:")
    LOGGER.info("%s/", paths.base)
    LOGGER.info(
        "├── raw_pdfs/                             "
        "← Stage 0 (--scrape): Downloaded bill PDFs"
    )
    LOGGER.info(
        "├── extracted_text/                       "
        "← Stage 1 (EXTRACT) or seeded from sample data"
    )
    LOGGER.info(
        "├── sample/                               "
        "← Generated test data (generate_sample_data.py)"
    )
    LOGGER.info("└── structured_output/")
    LOGGER.info("    ├── *_parsed.json                     ← Stages 2-4: Working files")
    LOGGER.info("    ├── validation_report.json            ← Stage 4: Validation results")
    LOGGER.info(
        "    ├── bills/                            "
        "← LAYER 1: One canonical file per bill"
    )
    LOGGER.info("    │   ├── HB25-1001_final.md")
    LOGGER.info("    │   └── ...")
    LOGGER.info(
        "    └── indices/                          "
        "← LAYER 2: Queryable index files"
    )
    LOGGER.info(
        "        ├── industry_index.json           "
        "← Stage 7: Bill → industries + NAICS codes"
    )
    LOGGER.info(
        "        ├── theme_index.json              "
        "← Stage 7: Theme → bills reverse index"
    )
    LOGGER.info(
        "        ├── crs_title_index.json          "
        "← Stage 5: CRS section → bills"
    )
    LOGGER.info(
        "        └── bill_graph.json               "
        "← Stage 5: Cross-reference network"
    )
    LOGGER.info(
        "%s/                               ← Static reference tables (built once)",
        taxonomy_dir,
    )
    LOGGER.info("├── crs_title_map.json")
    LOGGER.info("├── naics_hierarchy.json")
    LOGGER.info("├── keyword_to_naics.json")
    LOGGER.info("└── committee_to_naics.json")


def build_dry_run_results(
    stages: list[StageDefinition],
    start_stage: int,
    end_stage: int,
    sample: bool,
    scrape: bool,
    input_error: str | None = None,
) -> list[StageResult]:
    """Create stage results for a dry run without executing any stage."""
    results: list[StageResult] = []
    if input_error:
        results.append(StageResult(0, "INPUT CHECK", "blocked", error=input_error))
        results.extend(
            StageResult(stage.number, stage.name, "skipped") for stage in stages
        )
        return results

    if sample:
        results.append(StageResult(-1, "SAMPLE SEED", "dry-run"))
    if scrape:
        results.append(StageResult(0, "SCRAPE", "dry-run"))

    for stage in stages:
        if stage.number < start_stage or stage.number > end_stage:
            results.append(StageResult(stage.number, stage.name, "skipped"))
        elif sample and stage.number == 1:
            results.append(
                StageResult(
                    stage.number,
                    stage.name,
                    "skipped",
                    summary={"sample_mode": True, "reason": "already extracted"},
                )
            )
        else:
            results.append(StageResult(stage.number, stage.name, "dry-run"))
    return results


def build_stage_definitions(
    paths: PipelinePaths,
    final_format: str,
    taxonomy_dir: str,
) -> list[StageDefinition]:
    """Build numbered stage definitions.

    Args:
        paths: Pipeline path bundle.
        final_format: Output format for the formatter stage.
        taxonomy_dir: Directory containing taxonomy files.

    Returns:
        Ordered list of seven numbered pipeline stages.
    """
    return [
        StageDefinition(1, "EXTRACT", lambda: _run_extract_stage(paths)),
        StageDefinition(2, "PARSE", lambda: _run_parse_stage(paths)),
        StageDefinition(3, "ENRICH", lambda: _run_enrich_stage(paths)),
        StageDefinition(4, "VALIDATE", lambda: _run_validate_stage(paths)),
        StageDefinition(5, "GRAPH", lambda: _run_graph_stage(paths)),
        StageDefinition(6, "FORMAT", lambda: _run_format_stage(paths, final_format)),
        StageDefinition(7, "TAG", lambda: _run_tagging_stage(paths, taxonomy_dir)),
    ]


def execute_sample_seed(paths: PipelinePaths, dry_run: bool) -> StageResult:
    """Seed sample extracted JSON for sample-mode runs.

    Args:
        paths: Pipeline path bundle.
        dry_run: Whether to avoid mutating files.

    Returns:
        Stage result for the sample seeding step.
    """
    stage = StageDefinition(-1, "SAMPLE SEED", lambda: {})
    started_at = time.perf_counter()
    LOGGER.info("Seeding sample extracted JSON into %s.", paths.extracted_text)
    if dry_run:
        LOGGER.info(
            "DRY RUN: would copy sample extracted JSON from data/sample to %s.",
            paths.extracted_text,
        )
        return StageResult(-1, "SAMPLE SEED", "dry-run")

    try:
        from scripts.generate_sample_data import seed_pipeline

        summary = seed_pipeline(target_dir=str(paths.extracted_text))
        duration = time.perf_counter() - started_at
        LOGGER.info("Summary: %s", json.dumps(summary, indent=2))
        return StageResult(
            stage.number,
            stage.name,
            "completed",
            duration_seconds=duration,
            summary=summary,
        )
    except Exception as exc:
        duration = time.perf_counter() - started_at
        LOGGER.exception("Sample data seeding failed.")
        return StageResult(
            stage.number,
            stage.name,
            "failed",
            duration_seconds=duration,
            error=str(exc),
        )


def execute_stage(stage: StageDefinition) -> StageResult:
    """Execute one pipeline stage and return its result.

    Args:
        stage: Stage definition to execute.

    Returns:
        Stage result containing duration, summary, and status.
    """
    log_stage_header(stage)
    started_at = time.perf_counter()

    try:
        summary = stage.action()
        duration = time.perf_counter() - started_at
        normalized_summary = normalize_summary(summary)
        result = StageResult(
            stage.number,
            stage.name,
            "completed",
            duration_seconds=duration,
            summary=normalized_summary,
        )
        LOGGER.info("Summary: %s", json.dumps(normalized_summary, indent=2))
        LOGGER.info("Stage duration: %.2fs", duration)

        if stage_has_failures(normalized_summary):
            LOGGER.warning(
                "WARNING: %s completed with reported failures; continuing.",
                stage.name,
            )

        return result
    except KeyboardInterrupt:
        duration = time.perf_counter() - started_at
        raise KeyboardInterrupt(
            StageResult(
                stage.number,
                stage.name,
                "interrupted",
                duration_seconds=duration,
                error="KeyboardInterrupt",
            )
        )
    except Exception as exc:
        duration = time.perf_counter() - started_at
        LOGGER.exception("Stage %s failed; continuing to next stage.", stage.name)
        return StageResult(
            stage.number,
            stage.name,
            "failed",
            duration_seconds=duration,
            summary={},
            error=str(exc),
        )


def normalize_summary(summary: Any) -> Any:
    """Normalize a stage return value for display and final summaries.

    Args:
        summary: Raw return value from a pipeline module.

    Returns:
        JSON-friendly summary value.
    """
    if isinstance(summary, dict):
        return summary
    if isinstance(summary, list):
        return {"count": len(summary), "items": summary}
    return {"result": summary}


def stage_has_failures(summary: Any) -> bool:
    """Return whether a normalized summary reports failures.

    Args:
        summary: Normalized stage summary.

    Returns:
        True when common failure fields contain non-zero counts.
    """
    if not isinstance(summary, dict):
        return False

    failure_keys = {"fail", "failed", "failures", "errors"}
    for key, value in summary.items():
        if key.lower() in failure_keys and _numeric_value(value) > 0:
            return True
    return False


def log_stage_header(stage: StageDefinition) -> None:
    """Log a clear visible stage header.

    Args:
        stage: Stage being started.
    """
    if stage.number == 0:
        LOGGER.info("═══ STAGE 0: SCRAPE ═══")
    elif stage.number == 7:
        LOGGER.info("═══ STAGE 7/7: INDUSTRY TAGGING ═══")
    else:
        LOGGER.info("═══ STAGE %s/%s: %s ═══", stage.number, TOTAL_STAGES, stage.name)


def print_final_summary(
    results: list[StageResult],
    paths: PipelinePaths,
    final_format: str,
    total_seconds: float,
    data_mode: str,
    mode_used: str,
    sample: bool,
    dry_run: bool,
) -> None:
    """Print the end-of-run pipeline summary.

    Args:
        results: Stage results accumulated during the run.
        paths: Pipeline path bundle.
        final_format: Formatter output selection.
        total_seconds: Total elapsed pipeline time.
        data_mode: Human-readable input mode.
        mode_used: SAMPLE, LIVE, or RESUME.
        sample: Whether sample mode was used.
        dry_run: Whether this was only a dry-run plan.
    """
    tagging_summary = tagging_result_summary(results)
    LOGGER.info("")
    LOGGER.info("═══ FINAL SUMMARY ═══")
    LOGGER.info("Total pipeline execution time: %.2fs", total_seconds)
    LOGGER.info("Mode used: %s", mode_used)
    LOGGER.info("Data mode: %s", data_mode)
    LOGGER.info("Final output directory: %s", paths.structured_output)
    LOGGER.info(
        "Final formatted files in bills/: %s",
        count_final_files(paths.bills, final_format),
    )
    LOGGER.info("Total files in bills/: %s", count_total_files(paths.bills))
    LOGGER.info("Index files generated: %s", format_file_list(list_index_files(paths.indices)))
    LOGGER.info(
        "Tagging results: %s bills tagged",
        tagging_summary.get("tagged", 0),
    )
    LOGGER.info(
        "Scope breakdown: %s",
        format_breakdown(
            tagging_summary.get("scope_breakdown"),
            ("universal", "broad", "narrow", "targeted"),
        ),
    )
    LOGGER.info(
        "Confidence breakdown: %s",
        format_breakdown(
            tagging_summary.get("confidence_breakdown"),
            ("high", "moderate", "low"),
        ),
    )
    LOGGER.info("")
    LOGGER.info("Per-stage results:")

    for result in results:
        counts = summarize_success_failure_counts(result.summary)
        if result.status in {"failed", "interrupted", "blocked"}:
            counts["failure"] = max(counts["failure"], 1)
        LOGGER.info(
            "Stage %s %s: %s | %.2fs | success=%s failure=%s",
            result.number,
            result.name,
            result.status,
            result.duration_seconds,
            counts["success"],
            counts["failure"],
        )
        if result.error:
            LOGGER.info("  Error: %s", result.error)

    if sample and not dry_run and pipeline_completed_successfully(results):
        LOGGER.info(
            "Pipeline tested successfully with sample data. To run on real bills: "
            "python run_pipeline.py --scrape --session 2025a"
        )


def pipeline_completed_successfully(results: list[StageResult]) -> bool:
    """Return true when all executed stages completed without reported failures."""
    for result in results:
        if result.status in {"failed", "interrupted"}:
            return False
        if result.status == "completed" and stage_has_failures(result.summary):
            return False
    return True


def summarize_success_failure_counts(summary: Any) -> dict[str, int]:
    """Extract approximate success and failure counts from a stage summary.

    Args:
        summary: Normalized stage summary.

    Returns:
        Dictionary with ``success`` and ``failure`` integer counts.
    """
    counts = {"success": 0, "failure": 0}
    if not isinstance(summary, dict):
        return counts

    counts["failure"] = int(
        sum(
            _numeric_value(value)
            for key, value in summary.items()
            if key.lower() in {"fail", "failed", "failures", "errors"}
        )
    )

    success_keys = {
        "copied",
        "count",
        "downloaded",
        "generated",
        "processed",
        "tagged",
        "total_bills",
        "written",
        "pass",
    }
    counts["success"] = int(
        sum(
            _numeric_value(value)
            for key, value in summary.items()
            if key.lower() in success_keys
        )
    )
    return counts


def count_final_files(output_dir: Path, final_format: str) -> int:
    """Count final formatted files already present in the output directory.

    Args:
        output_dir: Canonical bills output directory.
        final_format: Requested final format.

    Returns:
        Number of matching final output files.
    """
    if not output_dir.exists():
        return 0

    patterns = {
        "markdown": ["*_final.md"],
        "json": ["*_final.json"],
        "both": ["*_final.md", "*_final.json"],
    }.get(final_format, ["*_final.md"])

    return sum(1 for pattern in patterns for _ in output_dir.glob(pattern))


def count_total_files(output_dir: Path) -> int:
    """Count all files in a directory without recursing."""
    if not output_dir.exists():
        return 0
    return sum(
        1
        for path in output_dir.iterdir()
        if path.is_file() and not path.name.startswith(".")
    )


def list_index_files(index_dir: Path) -> list[str]:
    """Return sorted index filenames generated under the indices directory."""
    if not index_dir.exists():
        return []
    return sorted(
        path.name
        for path in index_dir.iterdir()
        if path.is_file() and not path.name.startswith(".")
    )


def tagging_result_summary(results: list[StageResult]) -> dict[str, Any]:
    """Return the Stage 7 tagging summary, or an empty summary if absent."""
    for result in results:
        if result.number == 7 and isinstance(result.summary, dict):
            return result.summary
    return {}


def format_breakdown(value: Any, keys: tuple[str, ...]) -> str:
    """Format a deterministic count breakdown for final summaries."""
    if not isinstance(value, dict):
        value = {}
    return ", ".join(f"{key}={_numeric_value(value.get(key, 0))}" for key in keys)


def format_file_list(files: list[str]) -> str:
    """Format a list of files for compact summary display."""
    return ", ".join(files) if files else "None"


def _run_scrape_stage(session: str | None, paths: PipelinePaths) -> Any:
    """Run optional live scraping with a lazy module import."""
    if not session:
        raise ValueError("--session is required when --scrape is used.")
    from scripts import scraper

    return scraper.download_session(session=session, output_dir=str(paths.raw_pdfs))


def _run_extract_stage(paths: PipelinePaths) -> Any:
    """Run the extractor stage with a lazy module import."""
    from scripts import extractor

    return extractor.extract_all(
        input_dir=str(paths.raw_pdfs),
        output_dir=str(paths.extracted_text),
    )


def _run_parse_stage(paths: PipelinePaths) -> Any:
    """Run the parser stage with a lazy module import."""
    from scripts import bill_parser

    return bill_parser.parse_all(
        input_dir=str(paths.extracted_text),
        output_dir=str(paths.structured_output),
    )


def _run_enrich_stage(paths: PipelinePaths) -> Any:
    """Run the entity enrichment stage with a lazy module import."""
    from scripts import entity_extractor

    return entity_extractor.enrich_all(input_dir=str(paths.structured_output))


def _run_validate_stage(paths: PipelinePaths) -> Any:
    """Run the validation stage with a lazy module import."""
    from scripts import validator

    return validator.validate_all(input_dir=str(paths.structured_output))


def _run_graph_stage(paths: PipelinePaths) -> dict[str, Any]:
    """Build graph and CRS reverse-index files under the indices directory."""
    from scripts import graph_builder

    paths.indices.mkdir(parents=True, exist_ok=True)
    bills = graph_builder.load_all_bills(str(paths.structured_output))
    crs_index = graph_builder.build_crs_index(bills)
    graph = graph_builder.build_bill_graph(bills)
    clusters = graph_builder.find_clusters(graph)
    graph_builder.export_graph(graph, str(paths.indices / "bill_graph.json"))
    _write_json(paths.indices / "crs_title_index.json", crs_index)

    return {
        "total_bills": graph.number_of_nodes(),
        "total_edges": graph.number_of_edges(),
        "clusters": len(clusters),
        "largest_cluster_size": len(clusters[0]) if clusters else 0,
        "isolated_bills": sum(1 for node in graph.nodes if graph.degree(node) == 0),
        "index_files": ["bill_graph.json", "crs_title_index.json"],
    }


def _run_format_stage(paths: PipelinePaths, final_format: str) -> Any:
    """Run the formatter stage with a lazy module import."""
    from scripts import formatter

    return formatter.write_all(
        input_dir=str(paths.structured_output),
        output_dir=str(paths.bills),
        fmt=final_format,
    )


def _run_tagging_stage(paths: PipelinePaths, taxonomy_dir: str) -> Any:
    """Run the industry tagging stage with a lazy module import."""
    from scripts.industry_tagger import tag_all

    return tag_all(
        input_dir=str(paths.structured_output),
        taxonomy_dir=taxonomy_dir,
        output_dir=str(paths.indices),
    )


def _write_json(path: Path, payload: Any) -> None:
    """Write runtime JSON output with deterministic formatting."""
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def required_inputs_for_plan(
    start_stage: int,
    paths: PipelinePaths,
    sample: bool,
    scrape: bool,
) -> list[tuple[Path, str, str]]:
    """Return input requirements for the dry-run plan.

    Args:
        start_stage: Effective first numbered stage.
        paths: Pipeline path bundle.
        sample: Whether sample mode is active.
        scrape: Whether live scraping is active.

    Returns:
        Human-readable directory, pattern, and reason tuples.
    """
    if sample and start_stage <= 2:
        return [
            (
                Path("data/sample"),
                "*_extracted.json",
                "sample source files copied by seed_pipeline()",
            ),
            (
                paths.extracted_text,
                "*_extracted.json",
                "Stage 2 parser input after sample seeding",
            ),
        ]

    requirement = _stage_input_requirement(start_stage, paths, scrape)
    if requirement is None:
        return [
            (
                paths.raw_pdfs,
                "*.pdf",
                "created by Stage 0 SCRAPE before Stage 1 EXTRACT",
            )
        ]

    directory, pattern, suggestion = requirement
    return [(directory, pattern, suggestion)]


def _stage_input_requirement(
    start_stage: int,
    paths: PipelinePaths,
    scrape: bool,
) -> tuple[Path, str, str] | None:
    """Return the input requirement for a resume start stage."""
    requirements: dict[int, tuple[Path, str, str]] = {
        1: (
            paths.raw_pdfs,
            "*.pdf",
            "Use --sample for sample data or --scrape --session <session> for live PDFs.",
        ),
        2: (
            paths.extracted_text,
            "*_extracted.json",
            "Run Stage 1 extraction first, or use --sample to seed extracted JSON.",
        ),
        3: (
            paths.structured_output,
            "*_parsed.json",
            "Run Stage 2 parsing first.",
        ),
        4: (
            paths.structured_output,
            "*_parsed.json",
            "Run Stage 2 parsing first.",
        ),
        5: (
            paths.structured_output,
            "*_parsed.json",
            "Run Stage 2 parsing first.",
        ),
        6: (
            paths.structured_output,
            "*_parsed.json",
            "Run Stage 2 parsing first.",
        ),
        7: (
            paths.structured_output,
            "*_parsed.json",
            "Run Stage 2 parsing first.",
        ),
    }
    if start_stage == 1 and scrape:
        return None
    return requirements.get(start_stage)


def _has_files(directory: Path, pattern: str) -> bool:
    """Return whether a directory exists and contains a matching file."""
    return directory.exists() and any(directory.glob(pattern))


def _numeric_value(value: Any) -> int:
    """Best-effort conversion of a summary value into a count."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, list):
        return len(value)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Run the deterministic sample-first Project Geode pipeline."
    )
    parser.add_argument(
        "--session",
        help='Session to scrape when --scrape is used, such as "2025a".',
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help=(
            "Use generated sample data. Seeds data/extracted_text/ and starts "
            "at Stage 2 by default."
        ),
    )
    parser.add_argument(
        "--scrape",
        action="store_true",
        help="Run optional Stage 0 live PDF scraping before numbered stages.",
    )
    parser.add_argument(
        "--start-stage",
        type=int,
        default=None,
        help=(
            f"Stage number to resume from, 1 through {TOTAL_STAGES}. "
            "Default: 1, or 2 when --sample is set; existing-data mode "
            "auto-detects the earliest useful stage."
        ),
    )
    parser.add_argument(
        "--end-stage",
        type=int,
        default=TOTAL_STAGES,
        help=(
            f"Stage number to stop after, 1 through {TOTAL_STAGES}. "
            f"Default: {TOTAL_STAGES}."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json", "both"),
        default=DEFAULT_FINAL_FORMAT,
        help='Final output format. Default: "markdown".',
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Base data directory. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--taxonomy-dir",
        default=DEFAULT_TAXONOMY_DIR,
        help=f"Taxonomy directory. Default: {DEFAULT_TAXONOMY_DIR}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned stage run without executing modules.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the pipeline CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    paths = build_paths(args.output_dir)
    configure_logging(paths, verbose=args.verbose, dry_run=args.dry_run)

    try:
        run_pipeline(
            session=args.session,
            start_stage=args.start_stage,
            end_stage=args.end_stage,
            final_format=args.format,
            output_dir=args.output_dir,
            taxonomy_dir=args.taxonomy_dir,
            sample=args.sample,
            scrape=args.scrape,
            dry_run=args.dry_run,
        )
    except KeyboardInterrupt:
        LOGGER.warning("Pipeline interrupted by user.")
        return 130
    except (FileNotFoundError, ValueError) as exc:
        LOGGER.error("Pipeline configuration error: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
