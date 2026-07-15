"""Run and preserve the local-authority AI golden-question evaluation."""

from __future__ import annotations

import argparse
from pathlib import Path

from geode.orchestration import run_local_golden_evaluation
from geode.orchestration.services import LocalKnowledgeRetrievalBackend
from geode.utils.file_io import atomic_write_json


def write_local_golden_evaluation(root: Path) -> dict[str, object]:
    """Run the local pilot evaluation and write its machine-readable report."""

    summary = run_local_golden_evaluation(
        retrieval_backend=LocalKnowledgeRetrievalBackend(root)
    )
    payload = summary.model_dump(mode="json")
    payload["boundary"] = (
        "Local questions verify jurisdiction and limitation behavior. They do not certify "
        "unreviewed local legal meaning."
    )
    atomic_write_json(root / "_CONTROL_PLANE" / "LOCAL_GOLDEN_EVALUATION.json", payload, root)
    return payload


def main() -> None:
    """Run the local golden-question evaluation from the command line."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    payload = write_local_golden_evaluation(Path(args.root).resolve())
    print({"passed": payload["passed"], "failed": payload["failed"]})


if __name__ == "__main__":
    main()
