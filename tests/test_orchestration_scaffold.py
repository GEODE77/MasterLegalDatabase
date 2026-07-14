"""Default pytest entry point for orchestration scaffold tests."""

from geode.orchestration.tests.test_scaffold import (
    test_contracts_round_trip_and_export_json_schema,
    test_pipeline_runs_all_stubs_end_to_end,
    test_pipeline_short_circuits_after_halt,
)

__all__ = [
    "test_contracts_round_trip_and_export_json_schema",
    "test_pipeline_runs_all_stubs_end_to_end",
    "test_pipeline_short_circuits_after_halt",
]
