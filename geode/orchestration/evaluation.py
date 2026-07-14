"""Golden-question evaluation harness for orchestration integration."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from pydantic import Field

from geode.orchestration.contracts import (
    AuthorityLevel,
    Citation,
    CoverageRequirement,
    CoverageStatus,
    CurrencyMetadata,
    CurrencyStatus,
    EmittedAnswer,
    Evidence,
    GraphLink,
    Provenance,
    QueryState,
    QuestionType,
)
from geode.orchestration.contracts.models import StrictOrchestrationModel
from geode.orchestration.entrypoint import run_orchestration
from geode.orchestration.feedback import FeedbackLoop, FeedbackRecord
from geode.orchestration.services import FixtureRetrievalBackend, RetrievalBackend

GOLDEN_QUESTIONS_PATH = Path(__file__).parent / "config" / "golden_questions.json"


class GoldenQuestion(StrictOrchestrationModel):
    """One expected behavior row for end-to-end evaluation."""

    question_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    expected_question_type: QuestionType
    requires_local_limitation: bool = False


class EvalResult(StrictOrchestrationModel):
    """Pass or fail result for one golden question."""

    question_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    passed: bool
    checks: dict[str, bool] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class EvalSummary(StrictOrchestrationModel):
    """Evaluation summary across all golden questions."""

    total: int
    passed: int
    failed: int
    results: list[EvalResult]
    feedback_records: list[FeedbackRecord] = Field(default_factory=list)


def load_golden_questions(path: Path | None = None) -> list[GoldenQuestion]:
    """Load golden questions from the checked-in fixture file."""

    rows = json.loads((path or GOLDEN_QUESTIONS_PATH).read_text(encoding="utf-8"))
    return [
        GoldenQuestion.model_validate(
            {
                **row,
                "expected_question_type": QuestionType(str(row["expected_question_type"])),
            }
        )
        for row in rows
    ]


def build_mock_knowledge_backend() -> FixtureRetrievalBackend:
    """Build a deterministic fixture backend for integration and eval tests."""

    evidence = [
        _evidence(
            evidence_id="E-FED-GHG-REPORTING",
            category_id="federal_environmental_rules",
            citation_text="40 CFR Part 98",
            canonical_id="40_CFR_98",
            authority_level=AuthorityLevel.FEDERAL,
            text=(
                "Federal greenhouse gas reporting rules require covered facilities "
                "to report carbon dioxide and other greenhouse gas emissions."
            ),
        ),
        _evidence(
            evidence_id="E-CRS-AIR-AUTHORITY",
            category_id="colorado_statutes",
            citation_text="CRS 25-7-109",
            canonical_id="CRS-25-7-109",
            authority_level=AuthorityLevel.STATE,
            text=(
                "Colorado air pollution statutes authorize air quality control "
                "requirements for sources that emit air pollutants."
            ),
        ),
        _evidence(
            evidence_id="E-CCR-GHG-RULE",
            category_id="colorado_regulations",
            citation_text="5 CCR 1001-9",
            canonical_id="5_CCR_1001-9",
            authority_level=AuthorityLevel.STATE,
            text=(
                "Colorado regulations include greenhouse gas requirements for "
                "stationary sources and manufacturing operations."
            ),
            enabling_statute="CRS-25-7-109",
        ),
        _evidence(
            evidence_id="E-CCR-REPORTING",
            category_id="reporting_rules",
            citation_text="5 CCR 1001-9, Part C",
            canonical_id="5_CCR_1001-9_PART_C",
            authority_level=AuthorityLevel.STATE,
            text=(
                "Colorado reporting rules require regulated sources to submit "
                "emissions information for greenhouse gas and carbon dioxide releases."
            ),
            enabling_statute="CRS-25-7-109",
        ),
        _evidence(
            evidence_id="E-CCR-PERMIT",
            category_id="permitting_rules",
            citation_text="5 CCR 1001-5",
            canonical_id="5_CCR_1001-5",
            authority_level=AuthorityLevel.STATE,
            text=(
                "Colorado permitting rules require covered stationary sources to "
                "obtain air permits before emitting regulated air pollutants."
            ),
            enabling_statute="CRS-25-7-109",
        ),
        _evidence(
            evidence_id="E-CCR-SECTOR",
            category_id="sector_rules",
            citation_text="5 CCR 1001-20",
            canonical_id="5_CCR_1001-20",
            authority_level=AuthorityLevel.STATE,
            text=(
                "Manufacturing sector rules can impose operating, monitoring, and "
                "recordkeeping duties for industrial emission sources."
            ),
            enabling_statute="CRS-25-7-109",
        ),
    ]
    return FixtureRetrievalBackend(
        evidence=evidence,
        graph_links=[
            GraphLink(
                source_id="CRS-25-7-109",
                target_id="5_CCR_1001-9",
                relationship="implements",
            )
        ],
    )


def run_golden_evaluation(
    *,
    questions: list[GoldenQuestion] | None = None,
    retrieval_backend: RetrievalBackend | None = None,
    feedback_loop: FeedbackLoop | None = None,
    corpus_version: str = "mock-golden",
) -> EvalSummary:
    """Run all golden questions and return a pass/fail summary."""

    backend = retrieval_backend or build_mock_knowledge_backend()
    rows = questions or load_golden_questions()
    results = [
        evaluate_question(row, retrieval_backend=backend, corpus_version=corpus_version)
        for row in rows
    ]
    records: list[FeedbackRecord] = []
    if feedback_loop is not None:
        records = feedback_loop.capture_eval_results(
            [
                (result.question_id, result.query, result.passed, result.errors)
                for result in results
            ]
        )
    passed = sum(1 for result in results if result.passed)
    return EvalSummary(
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        results=results,
        feedback_records=records,
    )


def evaluate_question(
    question: GoldenQuestion,
    *,
    retrieval_backend: RetrievalBackend,
    corpus_version: str = "mock-golden",
) -> EvalResult:
    """Run and score one golden question."""

    state = run_orchestration(
        question.query,
        retrieval_backend=retrieval_backend,
        corpus_version=corpus_version,
    )
    checks = {
        "question_type": state.intent.question_type == question.expected_question_type,
        "coverage_completeness": _coverage_complete(state),
        "citation_validity": _gate_passed(state, "verify_citations")
        and bool(state.final_answer and state.final_answer.citations),
        "currency_correctness": _gate_passed(state, "verify_currency"),
        "schema_conformance": _schema_conforms(state),
        "local_limitation": (not question.requires_local_limitation)
        or _local_limitation_disclosed(state),
    }
    errors = [name for name, passed in checks.items() if not passed]
    return EvalResult(
        question_id=question.question_id,
        query=question.query,
        passed=all(checks.values()),
        checks=checks,
        errors=errors,
    )


def _evidence(
    *,
    evidence_id: str,
    category_id: str,
    citation_text: str,
    canonical_id: str,
    authority_level: AuthorityLevel,
    text: str,
    enabling_statute: str | None = None,
) -> Evidence:
    """Create one current mock evidence item."""

    return Evidence(
        evidence_id=evidence_id,
        text=text,
        citation=Citation(
            citation_text=citation_text,
            canonical_id=canonical_id,
            authority_level=authority_level,
        ),
        provenance=Provenance(
            source_id=canonical_id,
            source_path=f"mock://{canonical_id}",
            chain=[canonical_id],
        ),
        confidence=0.92,
        category_id=category_id,
        enabling_statute=enabling_statute,
        currency=CurrencyMetadata(
            effective_date=date(2024, 1, 1),
            status=CurrencyStatus.CURRENT,
            amendment_status="not_reported",
            repeal_status="not_reported",
        ),
        authority_level=authority_level,
    )


def _coverage_complete(state: QueryState) -> bool:
    """Return true when all required coverage categories were found."""

    if state.coverage_contract is None:
        return False
    return all(
        category.status == CoverageStatus.FOUND
        for category in state.coverage_contract.expected_categories
        if category.requirement == CoverageRequirement.REQUIRED
    )


def _gate_passed(state: QueryState, gate_name: str) -> bool:
    """Return true when the latest matching gate passed."""

    if state.verification_report is None:
        return False
    matches = [
        result
        for result in state.verification_report.gate_results
        if result.gate_name == gate_name
    ]
    return bool(matches and matches[-1].passed)


def _schema_conforms(state: QueryState) -> bool:
    """Validate the emitted answer with the strict Pydantic schema."""

    if state.emitted_answer is None:
        return False
    EmittedAnswer.model_validate_json(state.emitted_answer.model_dump_json())
    return True


def _local_limitation_disclosed(state: QueryState) -> bool:
    """Return true when county and municipal limitations are present."""

    if state.final_answer is None:
        return False
    text = " ".join(state.final_answer.uncertainties).casefold()
    return "county" in text and "municipal" in text
