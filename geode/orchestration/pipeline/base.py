"""Base stage contracts for the orchestration pipeline."""

from __future__ import annotations

from typing import Protocol

from geode.orchestration.contracts import QueryState


class Stage(Protocol):
    """Callable pipeline stage contract."""

    name: str

    def __call__(self, state: QueryState) -> QueryState:
        """Run the stage against a query state."""


class StageBase:
    """Minimal pass-through base class for scaffold stages."""

    name: str

    def __init__(self, name: str | None = None) -> None:
        """Create a stage with an optional explicit name."""

        self.name = name or self.__class__.__name__

    def __call__(self, state: QueryState) -> QueryState:
        """Return state unchanged."""

        return state
