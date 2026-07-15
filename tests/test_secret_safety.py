"""Secret safety check tests."""

from __future__ import annotations

from pathlib import Path

from geode.validation.secret_safety import is_text_candidate, scan_text


def test_detects_legiscan_api_key_assignment() -> None:
    """A real-looking API key assignment is blocked."""

    secret_value = "0123456789abcdef" * 2
    findings = scan_text("run.log", f"LEGISCAN_API_KEY={secret_value}\n")

    assert findings
    assert findings[0].redacted_value == "0123...cdef"


def test_ignores_placeholder_api_key() -> None:
    """Placeholder examples are allowed in docs and dashboards."""

    findings = scan_text("README.md", "LEGISCAN_API_KEY=<LEGISCAN_API_KEY>\n")

    assert findings == []


def test_detects_bearer_token() -> None:
    """Authorization bearer tokens are blocked."""

    token = "abcdef0123456789" * 2
    findings = scan_text("headers.txt", f"Authorization: Bearer {token}\n")

    assert findings
    assert findings[0].label == "bearer_token"


def test_ignores_sha_without_secret_context() -> None:
    """Normal hashes without key labels are not treated as secrets."""

    findings = scan_text("manifest.json", '"sha256": "' + ("a" * 64) + '"\n')

    assert findings == []


def test_ignores_provenance_hash_near_secretary_word() -> None:
    """Official source titles must not make provenance hashes look like tokens."""

    findings = scan_text(
        "index.jsonl",
        '{"title":"Secretary of State source","source_hash":"' + ("b" * 64) + '"}\n',
    )

    assert findings == []


def test_scans_expected_text_file_types() -> None:
    """Common Geode file types are included."""

    assert is_text_candidate(Path("record.jsonl"))
    assert is_text_candidate(Path("report.md"))
    assert not is_text_candidate(Path("source.pdf"))
