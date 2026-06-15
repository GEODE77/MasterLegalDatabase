"""Download orchestrator for Geode source connectors."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

from geode.connectors.ccr_scraper import download_all_rules
from geode.connectors.legiscan_client import download_all_sessions

LOGGER = logging.getLogger(__name__)

ConnectorFunction = Callable[[Path, dict[str, Any]], Any]


class ConnectorRunResult(BaseModel):
    """Result for one orchestrated connector."""

    model_config = ConfigDict(extra="forbid")

    connector: str
    status: str
    raw_dir: str
    message: str = ""


class OrchestratorReport(BaseModel):
    """Summary from a full or partial source download run."""

    model_config = ConfigDict(extra="forbid")

    root: str
    requested_connectors: list[str]
    results: list[ConnectorRunResult] = Field(default_factory=list)

    @property
    def failed(self) -> int:
        """Return number of failed connector runs."""

        return sum(1 for result in self.results if result.status == "failed")


def run_full_download(config: dict[str, Any]) -> OrchestratorReport:
    """Coordinate configured source connectors and raw archive organization."""

    root = Path(config.get("root", Path.cwd())).resolve()
    raw_root = root / "_RAW_ARCHIVE"
    raw_root.mkdir(parents=True, exist_ok=True)
    requested = list(config.get("connectors", ["ccr", "legiscan"]))
    injected = config.get("connector_functions", {})
    if not isinstance(injected, dict):
        raise ValueError("connector_functions must be a mapping")
    results = []
    for connector in requested:
        raw_dir = _raw_dir_for(raw_root, connector)
        raw_dir.mkdir(parents=True, exist_ok=True)
        runner = injected.get(connector, _default_runner(connector))
        if runner is None:
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
            runner(raw_dir, config)
        except Exception as exc:
            LOGGER.exception("Connector %s failed", connector)
            results.append(
                ConnectorRunResult(
                    connector=connector,
                    status="failed",
                    raw_dir=raw_dir.as_posix(),
                    message=str(exc),
                )
            )
            continue
        results.append(
            ConnectorRunResult(
                connector=connector,
                status="completed",
                raw_dir=raw_dir.as_posix(),
                message="completed",
            )
        )
    return OrchestratorReport(
        root=root.as_posix(),
        requested_connectors=requested,
        results=results,
    )


def _default_runner(connector: str) -> ConnectorFunction | None:
    """Return the default runner for a connector name."""

    if connector == "ccr":
        return _run_ccr
    if connector == "legiscan":
        return _run_legiscan
    return None


def _raw_dir_for(raw_root: Path, connector: str) -> Path:
    """Map connector names to raw archive directories."""

    mapping = {
        "ccr": "ccr",
        "legiscan": "legiscan",
        "register": "register",
        "exec_orders": "exec_orders",
        "coprrr": "supplementary/coprrr",
        "ag_opinions": "supplementary/ag_opinions",
    }
    return raw_root / mapping.get(connector, connector)


def _run_ccr(raw_dir: Path, config: dict[str, Any]) -> Any:
    """Run CCR downloader."""

    return download_all_rules(
        raw_dir,
        delay=float(config.get("delay", 1.0)),
        client=config.get("http_client"),
    )


def _run_legiscan(raw_dir: Path, config: dict[str, Any]) -> Any:
    """Run LegiScan downloader."""

    return download_all_sessions(
        raw_dir,
        api_key=config.get("legiscan_api_key"),
        client=config.get("http_client"),
        delay=float(config.get("delay", 0.25)),
    )
