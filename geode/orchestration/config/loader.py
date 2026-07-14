"""Load declarative orchestration rule config."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(__file__).parent


@cache
def load_orchestration_config() -> dict[str, Any]:
    """Load all orchestration rule config files."""

    return {
        "rules": _load_json_yaml(CONFIG_DIR / "rules.yaml"),
        "synonyms": _load_json_yaml(CONFIG_DIR / "synonyms.yaml"),
        "entities": _load_json_yaml(CONFIG_DIR / "entities.yaml"),
        "defaults": _load_json_yaml(CONFIG_DIR / "defaults.yaml"),
        "coverage": _load_json_yaml(CONFIG_DIR / "coverage.yaml"),
        "retrieval": _load_json_yaml(CONFIG_DIR / "retrieval.yaml"),
        "guardrails": _load_json_yaml(CONFIG_DIR / "guardrails.yaml"),
    }


def _load_json_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file written in JSON-compatible YAML."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"config file must contain an object: {path}")
    return payload
