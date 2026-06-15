"""Source fingerprinting helpers for the enhancement pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from geode.schemas.validators import require_official_source_url
from geode.utils.hashing import sha256_file


class SourceFingerprint(BaseModel):
    """Fingerprint metadata for an archived source file."""

    model_config = ConfigDict(extra="forbid")

    file_path: str
    source_url: HttpUrl
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=0)
    fingerprinted_at: datetime

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: HttpUrl) -> HttpUrl:
        """Require official or authorized source URLs."""

        require_official_source_url(str(value).rstrip("/"))
        return value


class PreservationReport(BaseModel):
    """Token preservation report for converted source text."""

    model_config = ConfigDict(extra="forbid")

    source_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    shared_tokens: int = Field(ge=0)
    preservation_score: float = Field(ge=0.0, le=1.0)
    passed: bool


def fingerprint_source(file_path: Path, source_url: str) -> SourceFingerprint:
    """Create a source fingerprint for an archived file."""

    return SourceFingerprint(
        file_path=file_path.as_posix(),
        source_url=source_url,
        sha256=sha256_file(file_path),
        size_bytes=file_path.stat().st_size,
        fingerprinted_at=datetime.now(timezone.utc),
    )


def compute_preservation_score(source_text: str, output_text: str) -> PreservationReport:
    """Compute preservation score as shared source tokens divided by source tokens."""

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
    return PreservationReport(
        source_tokens=len(source_tokens),
        output_tokens=len(output_tokens),
        shared_tokens=shared_count,
        preservation_score=score,
        passed=score >= 0.95,
    )


def verify_integrity(stored_hash: str, file_path: Path) -> bool:
    """Verify a file still matches a stored SHA-256 hash."""

    return sha256_file(file_path) == stored_hash

