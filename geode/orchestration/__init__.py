"""Scaffold for the Project Geode orchestration engine."""

from geode.orchestration.contracts import QueryState
from geode.orchestration.entrypoint import (
    DEFAULT_STAGE_ORDER,
    build_default_pipeline,
    build_default_stages,
    run_orchestration,
)
from geode.orchestration.evaluation import (
    EvalResult,
    EvalSummary,
    GoldenQuestion,
    build_mock_knowledge_backend,
    load_golden_questions,
    run_golden_evaluation,
)
from geode.orchestration.pipeline import Pipeline

__all__ = [
    "DEFAULT_STAGE_ORDER",
    "EvalResult",
    "EvalSummary",
    "GoldenQuestion",
    "Pipeline",
    "QueryState",
    "build_default_pipeline",
    "build_default_stages",
    "build_mock_knowledge_backend",
    "load_golden_questions",
    "run_golden_evaluation",
    "run_orchestration",
]
