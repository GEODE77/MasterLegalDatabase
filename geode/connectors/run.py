"""Command-line entry point for Geode bulk source downloads."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from geode.connectors.orchestrator import DEFAULT_CONNECTORS, OrchestratorReport, run_full_download
from geode.utils.logging import configure_logging

LOGGER = logging.getLogger(__name__)

CLOUD_SYNC_MARKERS = (
    "onedrive",
    "dropbox",
    "google drive",
    "googledrive",
    "iclouddrive",
    "box",
)

CONNECTOR_ALIASES = {
    "all": "all",
    "ccr": "ccr",
    "legiscan": "legiscan",
    "colorado_register": "colorado_register",
    "colorado-register": "colorado_register",
    "register": "colorado_register",
    "executive_orders": "executive_orders",
    "executive-orders": "executive_orders",
    "exec_orders": "executive_orders",
    "exec-orders": "executive_orders",
}


class BulkDownloadCommandError(ValueError):
    """Raised when the bulk-download command receives invalid options."""


def build_parser() -> argparse.ArgumentParser:
    """Build the bulk-download command parser."""

    parser = argparse.ArgumentParser(
        description="Download Colorado legal source artifacts into the Geode raw archive.",
    )
    parser.add_argument(
        "--connectors",
        "--sources",
        nargs="+",
        default=["all"],
        metavar="SOURCE",
        help=(
            "Sources to download. Accepts space-separated or comma-separated values. "
            "Choices: all, ccr, legiscan, colorado_register, executive_orders. "
            "Aliases: register, exec_orders."
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Project data root containing _RAW_ARCHIVE and _CONTROL_PLANE. Default: cwd.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        help="Seconds to wait between item downloads for connectors that support pacing.",
    )
    parser.add_argument(
        "--discovery-delay",
        type=float,
        help="Seconds to wait between CCR discovery pages.",
    )
    parser.add_argument(
        "--delay-jitter",
        type=float,
        help="Maximum jitter seconds added to --delay for paced item downloads.",
    )
    parser.add_argument(
        "--discovery-delay-jitter",
        type=float,
        help="Maximum jitter seconds added to --discovery-delay for CCR HTML pages.",
    )
    parser.add_argument(
        "--max-downloads",
        type=int,
        help=(
            "Maximum non-skipped download attempts per connector for this run. "
            "Skipped manifest-complete items do not count toward the cap."
        ),
    )
    parser.add_argument(
        "--http-timeout-seconds",
        type=float,
        help="HTTP request timeout for hardened connectors.",
    )
    parser.add_argument(
        "--http-max-retries",
        type=int,
        help="Maximum retry attempts for hardened connectors.",
    )
    parser.add_argument(
        "--http-base-delay",
        type=float,
        help="Initial retry backoff delay in seconds for hardened connectors.",
    )
    parser.add_argument(
        "--http-max-retry-delay-seconds",
        type=float,
        help="Maximum retry backoff delay in seconds for hardened connectors.",
    )
    parser.add_argument(
        "--http-retry-jitter-ratio",
        type=float,
        help="Maximum retry jitter as a ratio of --http-base-delay.",
    )
    parser.add_argument(
        "--legiscan-api-key",
        help="LegiScan API key. If omitted, LEGISCAN_API_KEY is used by the connector.",
    )
    parser.add_argument(
        "--register-index-url",
        help="Override Colorado Register index URL for diagnostics or controlled runs.",
    )
    parser.add_argument(
        "--executive-orders-index-url",
        help="Override executive-orders index URL for diagnostics or controlled runs.",
    )
    parser.add_argument(
        "--no-quality-report",
        action="store_true",
        help="Skip writing _CONTROL_PLANE/BULK_DOWNLOAD_QUALITY_REPORT.json.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full machine-readable orchestrator report instead of a text summary.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def config_from_args(args: argparse.Namespace) -> dict[str, Any]:
    """Convert parsed command arguments into an orchestrator config."""

    if args.max_downloads is not None and args.max_downloads < 0:
        raise BulkDownloadCommandError("--max-downloads cannot be negative")
    if args.delay is not None and args.delay < 0:
        raise BulkDownloadCommandError("--delay cannot be negative")
    if args.discovery_delay is not None and args.discovery_delay < 0:
        raise BulkDownloadCommandError("--discovery-delay cannot be negative")
    if args.delay_jitter is not None and args.delay_jitter < 0:
        raise BulkDownloadCommandError("--delay-jitter cannot be negative")
    if args.discovery_delay_jitter is not None and args.discovery_delay_jitter < 0:
        raise BulkDownloadCommandError("--discovery-delay-jitter cannot be negative")
    if args.http_retry_jitter_ratio is not None and args.http_retry_jitter_ratio < 0:
        raise BulkDownloadCommandError("--http-retry-jitter-ratio cannot be negative")

    config: dict[str, Any] = {
        "root": args.root,
        "connectors": _parse_connectors(args.connectors),
        "write_quality_report": not args.no_quality_report,
    }
    optional_values = {
        "delay": args.delay,
        "discovery_delay": args.discovery_delay,
        "delay_jitter": args.delay_jitter,
        "discovery_delay_jitter": args.discovery_delay_jitter,
        "max_downloads": args.max_downloads,
        "http_timeout_seconds": args.http_timeout_seconds,
        "http_max_retries": args.http_max_retries,
        "http_base_delay": args.http_base_delay,
        "http_max_retry_delay_seconds": args.http_max_retry_delay_seconds,
        "http_retry_jitter_ratio": args.http_retry_jitter_ratio,
        "legiscan_api_key": args.legiscan_api_key,
        "register_index_url": args.register_index_url,
        "executive_orders_index_url": args.executive_orders_index_url,
    }
    for key, value in optional_values.items():
        if value is not None:
            config[key] = value
    return config


def main(argv: list[str] | None = None) -> int:
    """Run the bulk-download command and return a process exit code."""

    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(logging.DEBUG if args.verbose else logging.INFO)

    try:
        config = config_from_args(args)
    except BulkDownloadCommandError as exc:
        parser.error(str(exc))

    _warn_if_storage_root_is_sensitive(Path(config["root"]))

    try:
        report = run_full_download(config)
    except Exception as exc:  # pragma: no cover - final CLI guard
        LOGGER.exception("Bulk download command failed: %s", exc)
        return 1

    _print_report(report, json_output=args.json)
    return _exit_code(report)


def _parse_connectors(values: list[str]) -> list[str]:
    """Parse and canonicalize connector selections."""

    tokens = [
        token.strip()
        for value in values
        for token in value.split(",")
        if token.strip()
    ]
    if not tokens:
        return list(DEFAULT_CONNECTORS)

    normalized = [_normalize_connector_token(token) for token in tokens]
    if "all" in normalized:
        if len(normalized) > 1:
            raise BulkDownloadCommandError("--connectors all cannot be combined with other sources")
        return list(DEFAULT_CONNECTORS)

    connectors: list[str] = []
    for connector in normalized:
        if connector not in DEFAULT_CONNECTORS:
            allowed = ", ".join(["all", *DEFAULT_CONNECTORS, "register", "exec_orders"])
            raise BulkDownloadCommandError(f"Unknown connector '{connector}'. Allowed: {allowed}")
        if connector not in connectors:
            connectors.append(connector)
    return connectors


def _normalize_connector_token(token: str) -> str:
    """Normalize one connector token or alias."""

    candidate = token.strip().lower()
    candidate = candidate.replace(" ", "_")
    if candidate in CONNECTOR_ALIASES:
        return CONNECTOR_ALIASES[candidate]
    return candidate


def _warn_if_storage_root_is_sensitive(root: Path) -> None:
    """Warn when bulk output is likely to churn Git or sync-managed folders."""

    resolved = root.resolve()
    if _is_inside_git_worktree(resolved):
        LOGGER.warning(
            "Bulk data root is inside a Git worktree: %s. Generated outputs are ignored, "
            "but large live runs are safer with --root outside the source checkout.",
            resolved,
        )
    if _is_inside_cloud_sync_root(resolved):
        LOGGER.warning(
            "Bulk data root appears to be inside a sync-managed folder: %s. "
            "For large live runs, use --root on a non-synced local data directory.",
            resolved,
        )


def _is_inside_git_worktree(path: Path) -> bool:
    """Return whether a path is at or below a directory containing .git."""

    return any((candidate / ".git").exists() for candidate in (path, *path.parents))


def _is_inside_cloud_sync_root(path: Path) -> bool:
    """Return whether a path appears to be inside a common sync provider folder."""

    return any(
        marker in part.casefold()
        for part in path.parts
        for marker in CLOUD_SYNC_MARKERS
    )


def _print_report(report: OrchestratorReport, *, json_output: bool) -> None:
    """Print a concise operational run summary."""

    if json_output:
        print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
        return

    summary = report.run_summary
    print("Bulk download run summary")
    print(f"Root: {report.root}")
    print(f"Connectors: {', '.join(report.requested_connectors)}")
    print(
        "Attempted: {attempted}  Succeeded: {succeeded}  "
        "Failed: {failed}  Skipped: {skipped}".format(**summary)
    )

    if report.quality_report_path:
        errors = report.quality_summary.get("errors", 0)
        warnings = report.quality_summary.get("warnings", 0)
        print(
            f"Quality report: {report.quality_report_path} "
            f"(errors={errors}, warnings={warnings})"
        )

    if summary["output_locations"]:
        print("Output locations:")
        for location in summary["output_locations"]:
            print(f"  - {location}")

    if report.results:
        print("Connector results:")
        for result in report.results:
            metrics = _metric_text(result.summary)
            metric_suffix = f" {metrics}" if metrics else ""
            print(f"  - {result.connector}: {result.status}{metric_suffix}")
            if result.status in {"failed", "skipped"} and result.message:
                print(f"    reason: {result.message}")


def _metric_text(summary: dict[str, Any]) -> str:
    """Return compact count text for one connector summary."""

    fields = []
    for key in (
        "discovered",
        "attempted",
        "downloaded",
        "failed",
        "blocked",
        "skipped",
        "retry_count",
    ):
        value = summary.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int | float):
            fields.append(f"{key}={int(value)}")
    if "bills" in summary and "downloaded" not in summary:
        bills = summary["bills"]
        if isinstance(bills, int | float) and not isinstance(bills, bool):
            fields.insert(0, f"bills={int(bills)}")
    return " ".join(fields)


def _exit_code(report: OrchestratorReport) -> int:
    """Return a shell exit code for the completed bulk run."""

    summary = report.run_summary
    if report.failed or summary["failed"] or report.quality_summary.get("errors", 0):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
