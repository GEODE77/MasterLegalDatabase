"""Hashing helpers for durable corpus fingerprints."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for a file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    """Return the SHA-256 digest for UTF-8 text."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def compute_sha256(file_path: Path) -> str:
    """Return the SHA-256 digest for a file."""

    return sha256_file(file_path)


def compute_preservation_score(source_text: str, output_text: str) -> dict[str, Any]:
    """Compute a token-overlap preservation score for converted text."""

    source_tokens = source_text.split()
    output_tokens = output_text.split()
    if not source_tokens:
        score = 1.0 if not output_tokens else 0.0
        shared_count = 0
    else:
        output_counts: dict[str, int] = {}
        for token in output_tokens:
            output_counts[token] = output_counts.get(token, 0) + 1
        shared_count = 0
        for token in source_tokens:
            available = output_counts.get(token, 0)
            if available:
                shared_count += 1
                output_counts[token] = available - 1
        score = shared_count / len(source_tokens)
    return {
        "source_tokens": len(source_tokens),
        "output_tokens": len(output_tokens),
        "shared_tokens": shared_count,
        "preservation_score": score,
    }
