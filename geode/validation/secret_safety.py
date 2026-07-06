"""Secret safety checks for staged Geode commits."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


SECRET_CONTEXT_RE = re.compile(
    r"(?i)(api[_-]?key|apikey|access[_-]?token|auth[_-]?token|client[_-]?secret|"
    r"password|secret|bearer|authorization|legiscan_api_key)"
)
ASSIGNMENT_RE = re.compile(
    r"(?i)(api[_-]?key|apikey|access[_-]?token|auth[_-]?token|client[_-]?secret|"
    r"password|secret|legiscan_api_key)"
    r"\s*[=:]\s*['\"]?([A-Za-z0-9._~+/=-]{20,})['\"]?"
)
JSON_ASSIGNMENT_RE = re.compile(
    r"(?i)\"([^\"]*(?:api[_-]?key|apikey|access[_-]?token|auth[_-]?token|"
    r"client[_-]?secret|password|secret|legiscan_api_key)[^\"]*)\""
    r"\s*:\s*\"([A-Za-z0-9._~+/=-]{20,})\""
)
BEARER_RE = re.compile(r"(?i)\bbearer\s+([A-Za-z0-9._~+/=-]{20,})")
URL_SECRET_RE = re.compile(
    r"(?i)[?&](api[_-]?key|access[_-]?token|auth[_-]?token|token|client[_-]?secret)="
    r"([^&\s\"']{20,})"
)
CONTEXT_HEX_RE = re.compile(r"\b[a-f0-9]{32,}\b")
PLACEHOLDER_RE = re.compile(r"^<[^>]+>$|^\$\{[^}]+}$|^REDACTED$|^CHANGEME$|^YOUR_.+", re.I)

TEXT_EXTENSIONS = {
    ".cfg",
    ".csv",
    ".env",
    ".ini",
    ".json",
    ".jsonl",
    ".log",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


@dataclass(frozen=True)
class SecretFinding:
    """A possible secret found in text about to be committed."""

    path: str
    line_number: int
    label: str
    redacted_value: str
    line_preview: str


def redact(value: str) -> str:
    """Return a safe preview of a suspected secret value."""

    clean = value.strip().strip("'\"")
    if len(clean) <= 8:
        return "*" * len(clean)
    return f"{clean[:4]}...{clean[-4:]}"


def is_placeholder(value: str) -> bool:
    """Return whether a value is an obvious non-secret placeholder."""

    return bool(PLACEHOLDER_RE.match(value.strip().strip("'\"")))


def is_text_candidate(path: Path) -> bool:
    """Return whether a file path should be scanned as text."""

    if path.name in {".env", ".env.local", ".env.example"}:
        return True
    return path.suffix.lower() in TEXT_EXTENSIONS


def scan_text(path: str, text: str) -> list[SecretFinding]:
    """Scan text and return possible committed secrets."""

    findings: list[SecretFinding] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        preview = line.strip()
        if not preview:
            continue
        matches: list[tuple[str, str]] = []
        matches.extend(("assignment", match.group(2)) for match in ASSIGNMENT_RE.finditer(line))
        matches.extend(("json_assignment", match.group(2)) for match in JSON_ASSIGNMENT_RE.finditer(line))
        matches.extend(("bearer_token", match.group(1)) for match in BEARER_RE.finditer(line))
        matches.extend(("url_token", match.group(2)) for match in URL_SECRET_RE.finditer(line))
        if SECRET_CONTEXT_RE.search(line):
            matches.extend(("context_hex_token", match.group(0)) for match in CONTEXT_HEX_RE.finditer(line))

        seen_values: set[str] = set()
        for label, value in matches:
            normalized = value.strip().strip("'\"")
            if normalized in seen_values or is_placeholder(normalized):
                continue
            seen_values.add(normalized)
            findings.append(
                SecretFinding(
                    path=path,
                    line_number=line_number,
                    label=label,
                    redacted_value=redact(normalized),
                    line_preview=_safe_line_preview(line),
                )
            )
    return findings


def scan_paths(paths: Iterable[Path]) -> list[SecretFinding]:
    """Scan normal working-tree paths for possible secrets."""

    findings: list[SecretFinding] = []
    for path in paths:
        if not path.exists() or not path.is_file() or not is_text_candidate(path):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        findings.extend(scan_text(str(path), text))
    return findings


def staged_paths(root: Path) -> list[str]:
    """Return staged paths that can add or modify content."""

    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMRT"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def staged_file_text(root: Path, path: str) -> str:
    """Return the staged version of a file."""

    result = subprocess.run(
        ["git", "show", f":{path}"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return result.stdout.decode("utf-8", errors="replace")


def scan_staged(root: Path) -> list[SecretFinding]:
    """Scan staged Git content for possible secrets."""

    findings: list[SecretFinding] = []
    for path_name in staged_paths(root):
        path = Path(path_name)
        if not is_text_candidate(path):
            continue
        findings.extend(scan_text(path_name, staged_file_text(root, path_name)))
    return findings


def format_findings(findings: Sequence[SecretFinding]) -> str:
    """Format findings for command-line output."""

    lines = [
        "Secret safety check failed.",
        "Possible API keys or tokens were found in staged content:",
    ]
    for finding in findings:
        lines.append(
            f"- {finding.path}:{finding.line_number} {finding.label} "
            f"{finding.redacted_value} | {finding.line_preview}"
        )
    lines.append("Remove the secret, use an environment variable, then stage again.")
    return "\n".join(lines)


def _safe_line_preview(line: str) -> str:
    """Return a short line preview without exposing full suspected secrets."""

    preview = line.strip()
    for match in CONTEXT_HEX_RE.finditer(preview):
        preview = preview.replace(match.group(0), redact(match.group(0)))
    if len(preview) > 140:
        return f"{preview[:137]}..."
    return preview


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root.")
    parser.add_argument("--staged", action="store_true", help="Scan staged Git content.")
    parser.add_argument("paths", nargs="*", type=Path, help="Optional working-tree paths to scan.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the secret safety check."""

    parser = build_parser()
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.staged:
        findings = scan_staged(root)
    else:
        findings = scan_paths(args.paths)

    if findings:
        print(format_findings(findings), file=sys.stderr)
        return 1
    print("Secret safety check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
