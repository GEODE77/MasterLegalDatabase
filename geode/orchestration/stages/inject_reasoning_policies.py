"""Load reasoning policies and render the model prompt."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Template

from geode.orchestration.contracts import DraftRequest, PromptPacket, QueryState, StageLog, StageStatus
from geode.orchestration.services import PromptPrefixBuilder
from geode.orchestration.stages._stub import PassThroughStage

POLICY_DIR = Path(__file__).parents[1] / "policies"
PROMPT_TEMPLATE = POLICY_DIR / "draft_prompt.md.j2"


class InjectReasoningPoliciesStage(PassThroughStage):
    """Assemble advisory model policy and prompt text."""

    def __call__(self, state: QueryState) -> QueryState:
        """Load markdown policies and render deterministic prompt packet."""

        policies = _load_policies()
        template = Template(PROMPT_TEMPLATE.read_text(encoding="utf-8"))
        rendered_prompt = template.render(
            intent=state.intent,
            evidence=state.evidence,
            conflicts=state.conflicts,
            policies=policies,
            empty_expected_categories=state.empty_expected_categories,
        )
        stable_prompt = PromptPrefixBuilder().split_rendered(rendered_prompt)
        packet = PromptPacket(
            policies=policies,
            rendered_prompt=rendered_prompt,
            evidence_ids=[item.evidence_id for item in state.evidence],
            stable_prefix=stable_prompt.stable_prefix,
            dynamic_suffix=stable_prompt.dynamic_suffix,
            stable_prefix_hash=stable_prompt.prefix_hash,
            stable_prefix_tokens=stable_prompt.prefix_tokens,
            provider_cache_settings=stable_prompt.cache_settings.__dict__,
        )
        state.prompt_packet = packet
        state.draft_request = DraftRequest(
            prompt=rendered_prompt,
            evidence=state.evidence,
            conflicts=state.conflicts,
        )
        state.trace.append(
            StageLog(
                stage_name=self.name,
                status=StageStatus.PASSED,
                message="Reasoning policies loaded and prompt rendered.",
                completed_at=datetime.now(timezone.utc),
                details={
                    "policy_files": sorted(policies),
                    "evidence_ids": packet.evidence_ids,
                },
            )
        )
        return state


def _load_policies() -> dict[str, str]:
    """Load model-facing policy markdown from disk."""

    policies: dict[str, str] = {}
    for path in sorted(POLICY_DIR.glob("*.md")):
        policies[path.name] = path.read_text(encoding="utf-8").strip()
    return policies
