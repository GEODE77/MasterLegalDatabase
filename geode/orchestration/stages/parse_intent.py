"""Parse high-level intent using configured deterministic rules."""

from datetime import datetime, timezone
from typing import Any

from geode.orchestration.config import load_orchestration_config
from geode.orchestration.contracts import (
    AnswerShape,
    Industry,
    QueryState,
    QuestionType,
    StageLog,
    StageStatus,
    Topic,
)
from geode.orchestration.stages._stub import PassThroughStage


class ParseIntentStage(PassThroughStage):
    """Classify the query intent from configured terms."""

    def __call__(self, state: QueryState) -> QueryState:
        """Populate topic, sub-topic, industry, question type, and answer shape."""

        config = load_orchestration_config()["rules"]["classification"]
        query = (state.intent.normalized_query or state.intent.raw_query).casefold()
        question_rule = _first_matching_rule(config["question_type_rules"], query)
        topic_rule = _first_matching_rule(config["topic_rules"], query)
        industry_rule = _first_matching_rule(config["industry_rules"], query)

        if question_rule:
            state.intent.question_type = QuestionType(str(question_rule["question_type"]))
            state.intent.answer_shape = AnswerShape(str(question_rule["answer_shape"]))
        if topic_rule:
            state.intent.topic = Topic(str(topic_rule["topic"]))
            state.intent.sub_topic = str(topic_rule["sub_topic"])
        if industry_rule:
            state.intent.industry = Industry(str(industry_rule["industry"]))

        state.trace.append(
            StageLog(
                stage_name=self.name,
                status=StageStatus.PASSED,
                message="Intent classified with configured deterministic rules.",
                completed_at=datetime.now(timezone.utc),
                details={
                    "question_type": state.intent.question_type.value,
                    "answer_shape": state.intent.answer_shape.value,
                    "topic": state.intent.topic.value,
                    "sub_topic": state.intent.sub_topic,
                    "industry": state.intent.industry.value,
                },
            )
        )
        return state


def _first_matching_rule(rules: list[dict[str, Any]], query: str) -> dict[str, Any] | None:
    """Return the first configured rule with any term in the query."""

    for rule in rules:
        terms = [str(term).casefold() for term in rule.get("any_terms", [])]
        if any(term in query for term in terms):
            return rule
    return None
