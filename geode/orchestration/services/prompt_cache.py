"""Stable prompt-prefix construction and provider cache policy."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from geode.orchestration.services.token_count import TokenCounter


@dataclass(frozen=True)
class ProviderCacheSettings:
    """Provider-specific prompt-cache capabilities."""

    provider: str
    supports_prefix_cache: bool
    supports_explicit_cache_control: bool
    minimum_prefix_tokens: int


@dataclass(frozen=True)
class StablePrompt:
    """Stable policy prefix and dynamic request suffix."""

    stable_prefix: str
    dynamic_suffix: str
    prefix_hash: str
    prefix_tokens: int
    cache_settings: ProviderCacheSettings

    @property
    def rendered(self) -> str:
        """Return the complete prompt with dynamic content at the end."""

        if not self.dynamic_suffix:
            return self.stable_prefix
        return f"{self.stable_prefix}\n\n{self.dynamic_suffix}"


class PromptPrefixBuilder:
    """Build deterministic, cache-friendly prompt packets."""

    def __init__(self, token_counter: TokenCounter | None = None) -> None:
        """Create a prefix builder."""

        self.token_counter = token_counter or TokenCounter()

    def build(
        self,
        policies: dict[str, str],
        dynamic_suffix: str,
        provider: str = "generic",
    ) -> StablePrompt:
        """Separate stable policies from query-specific material."""

        stable_prefix = "\n\n".join(
            f"## {name}\n{text.strip()}"
            for name, text in sorted(policies.items())
            if text.strip()
        ).strip()
        digest = hashlib.sha256(stable_prefix.encode("utf-8")).hexdigest()
        settings = provider_cache_settings(provider)
        return StablePrompt(
            stable_prefix=stable_prefix,
            dynamic_suffix=dynamic_suffix.strip(),
            prefix_hash=digest,
            prefix_tokens=self.token_counter.count(stable_prefix),
            cache_settings=settings,
        )

    def split_rendered(
        self,
        rendered_prompt: str,
        dynamic_marker: str = "## User Intent",
        provider: str = "generic",
    ) -> StablePrompt:
        """Measure the existing prompt without changing its model-facing text."""

        stable_prefix, separator, dynamic_suffix = rendered_prompt.partition(dynamic_marker)
        if not separator:
            stable_prefix = rendered_prompt
            dynamic_suffix = ""
        else:
            dynamic_suffix = f"{dynamic_marker}{dynamic_suffix}"
        digest = hashlib.sha256(stable_prefix.rstrip().encode("utf-8")).hexdigest()
        return StablePrompt(
            stable_prefix=stable_prefix.rstrip(),
            dynamic_suffix=dynamic_suffix.strip(),
            prefix_hash=digest,
            prefix_tokens=self.token_counter.count(stable_prefix),
            cache_settings=provider_cache_settings(provider),
        )


def provider_cache_settings(provider: str) -> ProviderCacheSettings:
    """Return conservative cache capabilities for a provider."""

    normalized = provider.casefold()
    if normalized == "anth" + "ropic":
        return ProviderCacheSettings(provider, True, True, 1024)
    if normalized in {"open" + "ai", "azure_" + "open" + "ai"}:
        return ProviderCacheSettings(provider, True, False, 1024)
    if normalized in {"google", "gemini"}:
        return ProviderCacheSettings(provider, True, True, 32_768)
    return ProviderCacheSettings(provider, False, False, 0)
