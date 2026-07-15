"""Download orchestrator for Geode source connectors."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

from geode.connectors.archive_paths import raw_connector_dir
from geode.connectors.ccr_scraper import download_all_rules
from geode.connectors.exec_orders_scraper import download_all_executive_orders
from geode.connectors.legiscan_client import download_all_sessions
from geode.connectors.quality import (
    build_bulk_download_quality_report,
    write_bulk_download_quality_report,
)
from geode.connectors.register_scraper import download_all_publications
from geode.connectors.local_sources import download_pilot_sources

LOGGER = logging.getLogger(__name__)

ConnectorFunction = Callable[[Path, dict[str, Any]], Any]
DEFAULT_CONNECTORS = ["ccr", "legiscan", "colorado_register", "executive_orders"]


class ConnectorRunResult(BaseModel):
    """Result for one orchestrated connector."""

    model_config = ConfigDict(extra="forbid")

    connector: str
    status: str
    raw_dir: str
    message: str = ""
    summary: dict[str, Any] = Field(default_factory=dict)


class OrchestratorReport(BaseModel):
    """Summary from a full or partial source download run."""

    model_config = ConfigDict(extra="forbid")

    root: str
    requested_connectors: list[str]
    results: list[ConnectorRunResult] = Field(default_factory=list)
    quality_report_path: str | None = None
    quality_summary: dict[str, int] = Field(default_factory=dict)

    @property
    def failed(self) -> int:
        """Return number of failed connector runs."""

        return sum(1 for result in self.results if result.status == "failed")

    @property
    def run_summary(self) -> dict[str, Any]:
        """Return aggregate item counts and output locations for the run."""

        return _aggregate_results(self.results)


def run_full_download(config: dict[str, Any]) -> OrchestratorReport:
    """Coordinate configured source connectors and raw archive organization."""

    root = Path(config.get("root", Path.cwd())).resolve()
    raw_root = root / "_RAW_ARCHIVE"
    raw_root.mkdir(parents=True, exist_ok=True)
    requested = _requested_connectors(config)
    injected = config.get("connector_functions", {})
    if not isinstance(injected, dict):
        raise ValueError("connector_functions must be a mapping")
    LOGGER.info(
        "Bulk download started connectors=%s raw_root=%s",
        ",".join(requested),
        raw_root.as_posix(),
    )
    results = []
    for connector in requested:
        raw_dir = _raw_dir_for(raw_root, connector)
        raw_dir.mkdir(parents=True, exist_ok=True)
        runner = injected.get(connector, _default_runner(connector))
        LOGGER.info("Connector started connector=%s raw_dir=%s", connector, raw_dir.as_posix())
        if runner is None:
            LOGGER.warning(
                "Connector skipped connector=%s raw_dir=%s reason=%s",
                connector,
                raw_dir.as_posix(),
                "No default runner configured.",
            )
            results.append(
                ConnectorRunResult(
                    connector=connector,
                    status="skipped",
                    raw_dir=raw_dir.as_posix(),
                    message="No default runner configured.",
                )
            )
            continue
        try:
            summary = _summarize_runner_output(runner(raw_dir, config))
        except Exception as exc:
            LOGGER.exception(
                "Connector failed connector=%s raw_dir=%s reason=%s",
                connector,
                raw_dir.as_posix(),
                exc,
            )
            results.append(
                ConnectorRunResult(
                    connector=connector,
                    status="failed",
                    raw_dir=raw_dir.as_posix(),
                    message=str(exc),
                )
            )
            continue
        status = "completed_with_errors" if _summary_has_errors(summary) else "completed"
        metrics = _connector_metrics(summary)
        LOGGER.info(
            "Connector completed connector=%s status=%s attempted=%s succeeded=%s "
            "failed=%s skipped=%s raw_dir=%s manifest=%s",
            connector,
            status,
            metrics["attempted"],
            metrics["succeeded"],
            metrics["failed"],
            metrics["skipped"],
            raw_dir.as_posix(),
            summary.get("manifest_path", ""),
        )
        results.append(
            ConnectorRunResult(
                connector=connector,
                status=status,
                raw_dir=raw_dir.as_posix(),
                message=status.replace("_", " "),
                summary=summary,
            )
        )
    report = OrchestratorReport(
        root=root.as_posix(),
        requested_connectors=requested,
        results=results,
    )
    run_summary = report.run_summary
    log_summary = LOGGER.warning if run_summary["failed"] else LOGGER.info
    log_summary(
        "Bulk download summary attempted=%s succeeded=%s failed=%s skipped=%s "
        "outputs=%s",
        run_summary["attempted"],
        run_summary["succeeded"],
        run_summary["failed"],
        run_summary["skipped"],
        ",".join(run_summary["output_locations"]),
    )
    if config.get("write_quality_report", True):
        quality_report = build_bulk_download_quality_report(root, report.results)
        quality_report_path = write_bulk_download_quality_report(root, quality_report)
        report.quality_report_path = quality_report_path.as_posix()
        report.quality_summary = quality_report.summary
        quality_log = LOGGER.warning if not quality_report.valid else LOGGER.info
        quality_log(
            "Bulk download quality report valid=%s errors=%s warnings=%s path=%s",
            quality_report.valid,
            quality_report.summary["errors"],
            quality_report.summary["warnings"],
            report.quality_report_path,
        )
    return report


def _default_runner(connector: str) -> ConnectorFunction | None:
    """Return the default runner for a connector name."""

    canonical = _canonical_connector(connector)
    if canonical == "ccr":
        return _run_ccr
    if canonical == "legiscan":
        return _run_legiscan
    if canonical == "colorado_register":
        return _run_register
    if canonical == "executive_orders":
        return _run_executive_orders
    if canonical in {"local", "county", "district"}:
        return _run_local
    return None


def _raw_dir_for(raw_root: Path, connector: str) -> Path:
    """Map connector names to raw archive directories."""

    return raw_connector_dir(raw_root, _canonical_connector(connector))


def _run_ccr(raw_dir: Path, config: dict[str, Any]) -> Any:
    """Run CCR downloader."""

    return download_all_rules(
        raw_dir,
        delay=float(config.get("delay", 1.0)),
        client=config.get("http_client"),
        discovery_delay=float(config.get("discovery_delay", 0.0)),
        delay_jitter_seconds=float(config.get("delay_jitter", 0.0)),
        discovery_delay_jitter_seconds=float(config.get("discovery_delay_jitter", 0.0)),
        max_downloads=_optional_int(config, "max_downloads"),
        **_http_options(config),
    )


def _run_legiscan(raw_dir: Path, config: dict[str, Any]) -> Any:
    """Run LegiScan downloader."""

    return download_all_sessions(
        raw_dir,
        api_key=config.get("legiscan_api_key"),
        client=config.get("http_client"),
        delay=float(config.get("delay", 0.25)),
        max_downloads=_optional_int(config, "max_downloads"),
    )


def _run_register(raw_dir: Path, config: dict[str, Any]) -> Any:
    """Run Colorado Register downloader."""

    kwargs: dict[str, Any] = {
        "delay": float(config.get("delay", 1.0)),
        "client": config.get("http_client"),
        "max_downloads": _optional_int(config, "max_downloads"),
        **_http_options(config),
    }
    if config.get("register_index_url"):
        kwargs["index_url"] = str(config["register_index_url"])
    return download_all_publications(raw_dir, **kwargs)


def _run_executive_orders(raw_dir: Path, config: dict[str, Any]) -> Any:
    """Run executive order downloader."""

    kwargs: dict[str, Any] = {
        "delay": float(config.get("delay", 1.0)),
        "client": config.get("http_client"),
        "max_downloads": _optional_int(config, "max_downloads"),
        **_http_options(config),
    }
    if config.get("executive_orders_index_url"):
        kwargs["index_url"] = str(config["executive_orders_index_url"])
    return download_all_executive_orders(raw_dir, **kwargs)


def _run_local(raw_dir: Path, config: dict[str, Any]) -> Any:
    """Run the bounded county and district pilot connector."""

    return download_pilot_sources(
        raw_dir.parents[1],
        authority_level=config.get("local_authority_level"),
        dry_run=bool(config.get("dry_run", False)),
        max_links_per_source=int(config.get("local_max_links", 25)),
        timeout_seconds=float(config.get("timeout", 30.0)),
    )


def _requested_connectors(config: dict[str, Any]) -> list[str]:
    """Return normalized connector names requested by a run config."""

    requested = config.get("connectors", DEFAULT_CONNECTORS)
    if requested == "all":
        return list(DEFAULT_CONNECTORS)
    if isinstance(requested, str):
        return [requested]
    return list(requested)


def _canonical_connector(connector: str) -> str:
    """Normalize source-registry and legacy connector names."""

    aliases = {
        "register": "colorado_register",
        "exec_orders": "executive_orders",
    }
    return aliases.get(connector, connector)


def _summarize_runner_output(output: Any) -> dict[str, Any]:
    """Convert connector return values into JSON-friendly run summaries."""

    if isinstance(output, BaseModel):
        return output.model_dump(mode="json")
    if isinstance(output, dict):
        return dict(output)
    if isinstance(output, list):
        return {"count": len(output)}
    if output is None:
        return {}
    return {"result": str(output)}


def _summary_has_errors(summary: dict[str, Any]) -> bool:
    """Return whether a connector summary reports item-level failures."""

    failed = summary.get("failed", 0)
    if isinstance(failed, int | float) and failed > 0:
        return True
    errors = summary.get("errors")
    return isinstance(errors, list) and len(errors) > 0


def _aggregate_results(results: list[ConnectorRunResult]) -> dict[str, Any]:
    """Aggregate connector summaries into one operational run summary."""

    aggregate = {
        "attempted": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped": 0,
        "output_locations": [],
    }
    output_locations: list[str] = []
    for result in results:
        metrics = _connector_metrics(result.summary)
        if result.status == "failed" and metrics["failed"] == 0:
            metrics["failed"] = 1
            metrics["attempted"] = max(metrics["attempted"], 1)
        if result.status == "skipped" and metrics["skipped"] == 0:
            metrics["skipped"] = 1
        aggregate["attempted"] += metrics["attempted"]
        aggregate["succeeded"] += metrics["succeeded"]
        aggregate["failed"] += metrics["failed"]
        aggregate["skipped"] += metrics["skipped"]
        for location in _output_locations(result):
            if location not in output_locations:
                output_locations.append(location)
    aggregate["output_locations"] = output_locations
    return aggregate


def _connector_metrics(summary: dict[str, Any]) -> dict[str, int]:
    """Return attempted, succeeded, failed, and skipped counts from a connector summary."""

    skipped = _int_summary_value(summary, "skipped")
    failed = _int_summary_value(summary, "failed")
    succeeded = _int_summary_value(summary, "downloaded")
    if succeeded == 0 and "bills" in summary:
        succeeded = max(_int_summary_value(summary, "bills") - skipped, 0)
    attempted = _int_summary_value(summary, "attempted")
    if "attempted" not in summary:
        attempted = max(
            _int_summary_value(summary, "discovered"),
            succeeded + skipped + failed,
        )
    return {
        "attempted": attempted,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
    }


def _int_summary_value(summary: dict[str, Any], key: str) -> int:
    """Return a non-negative integer summary value."""

    value = summary.get(key, 0)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float):
        return max(int(value), 0)
    return 0


def _output_locations(result: ConnectorRunResult) -> list[str]:
    """Return concise output locations for a connector result."""

    locations = [result.raw_dir]
    for key in ("archive_dir", "manifest_path"):
        value = result.summary.get(key)
        if isinstance(value, str) and value:
            locations.append(value)
    for key in ("failure_manifest_path", "summary_path", "checkpoint_path", "log_path"):
        value = result.summary.get(key)
        if isinstance(value, str) and value:
            locations.append(value)
    return locations


def _http_options(config: dict[str, Any]) -> dict[str, Any]:
    """Extract optional hardened HTTP settings from orchestrator config."""

    options: dict[str, Any] = {}
    int_fields = {
        "http_max_retries": "max_retries",
    }
    float_fields = {
        "http_base_delay": "base_delay",
        "http_timeout_seconds": "timeout_seconds",
        "http_max_retry_delay_seconds": "max_retry_delay_seconds",
        "http_retry_jitter_ratio": "retry_jitter_ratio",
    }
    for config_key, option_key in int_fields.items():
        if config.get(config_key) is not None:
            options[option_key] = int(config[config_key])
    for config_key, option_key in float_fields.items():
        if config.get(config_key) is not None:
            options[option_key] = float(config[config_key])
    return options


def _optional_int(config: dict[str, Any], key: str) -> int | None:
    """Return an optional integer config value."""

    if config.get(key) is None:
        return None
    return int(config[key])
