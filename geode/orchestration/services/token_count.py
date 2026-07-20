"""Model-aware token counting with a deterministic dependency-free fallback."""

from __future__ import annotations

import importlib
import math
import re
from dataclasses import dataclass
from typing import Any, Protocol, cast


class TokenEncoding(Protocol):
    """Minimal interface required from an optional tokenizer encoding."""

    def encode(self, text: str, *, disallowed_special: tuple[()]) -> list[int]:
        """Encode text into model tokens."""


@dataclass(frozen=True)
class TokenCounter:
    """Count model input tokens using an optional provider tokenizer."""

    model: str = "default"
    provider: str = "generic"

    @property
    def name(self) -> str:
        """Return the tokenizer name used for accounting."""

        if self._encoding() is not None:
            return f"tiktoken:{self.model}"
        return "fallback:wordpiece-estimate"

    def count(self, text: str) -> int:
        """Return a positive token estimate for non-empty text."""

        if not text:
            return 0
        encoding = self._encoding()
        if encoding is not None:
            return len(encoding.encode(text, disallowed_special=()))
        return _fallback_count(text)

    def _encoding(self) -> TokenEncoding | None:
        """Load a tiktoken encoding when the optional package is installed."""

        try:
            tiktoken: Any = importlib.import_module("tiktoken")
        except ImportError:
            return None
        try:
            return cast(TokenEncoding, tiktoken.encoding_for_model(self.model))
        except (KeyError, ValueError):
            try:
                return cast(TokenEncoding, tiktoken.get_encoding("cl100k_base"))
            except (KeyError, ValueError):
                return None


def _fallback_count(text: str) -> int:
    """Estimate subword tokens without adding a model-tokenizer dependency."""

    pieces = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
    total = 0
    for piece in pieces:
        if piece.isalnum() or "_" in piece:
            total += max(1, math.ceil(len(piece) / 4))
        else:
            total += 1
    return max(1, total)
