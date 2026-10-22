from __future__ import annotations

import json

from slice_runner.infrastructure.activity_payload import ActivityPayload
from slice_runner.infrastructure.call_spend_payload import CallSpendPayload
from slice_runner.infrastructure.corpus_diff_payload import CorpusDiffPayload
from slice_runner.infrastructure.corpus_verdict_payload import CorpusVerdictPayload
from slice_runner.infrastructure.debt_payload import DebtPayload
from slice_runner.infrastructure.event_payload import EventPayload
from slice_runner.infrastructure.harness_call_payload import HarnessCallPayload
from slice_runner.infrastructure.metrics_entry_payload import MetricsEntryPayload
from slice_runner.infrastructure.tool_use_payload import CallToolUsePayload, UnrecordedCallToolUsePayload


class TestEveryDurableLogDeclaresASchemaAProgramCanRead:
    def test_the_call_trace_schema_requires_the_identity_of_the_call(self) -> None:
        required = self._required(HarnessCallPayload.json_schema())

        assert required == {"ts", "repo", "issue", "slice_id", "step", "session"}

    def test_the_spend_log_schema_requires_the_session_and_the_spend_it_carries(self) -> None:
        assert self._required(CallSpendPayload.json_schema()) == {"ts", "repo", "issue", "slice_id", "session", "spend"}

    def test_the_metrics_log_schema_requires_the_identity_and_the_closure_of_the_slice(self) -> None:
        required = self._required(MetricsEntryPayload.json_schema())

        assert {"ts", "repo", "issue", "slice_id", "name", "verdict", "ci"} <= required

    def test_the_corpus_verdict_schema_requires_the_slice_and_the_verdict_the_judge_gave(self) -> None:
        assert self._required(CorpusVerdictPayload.json_schema()) == {
            "ts",
            "repo",
            "issue",
            "slice_id",
            "verify_round",
            "session",
            "verdict",
            "severity_counts",
            "diff_stats",
        }

    def test_the_corpus_diff_schema_requires_the_slice_and_the_diff_that_was_judged(self) -> None:
        assert self._required(CorpusDiffPayload.json_schema()) == {
            "ts",
            "repo",
            "issue",
            "slice_id",
            "verify_round",
            "session",
            "diff",
        }

    def test_the_debt_ledger_schema_requires_the_slice_and_what_was_left_out(self) -> None:
        assert self._required(DebtPayload.json_schema()) == {"ts", "repo", "issue", "slice_id", "left_out"}

    def test_the_tool_use_schema_requires_the_identity_of_the_call_and_the_uses_it_carries(self) -> None:
        assert self._required(CallToolUsePayload.json_schema()) == {
            "ts",
            "repo",
            "issue",
            "slice_id",
            "step",
            "session",
            "uses",
        }

    def test_the_unrecorded_tool_use_schema_requires_the_identity_of_the_call_and_the_cause(self) -> None:
        assert self._required(UnrecordedCallToolUsePayload.json_schema()) == {
            "ts",
            "repo",
            "issue",
            "slice_id",
            "step",
            "session",
            "cause",
        }

    def test_the_event_schema_requires_the_coordinates_the_standing_the_rounds_the_spend_and_the_budget(
        self,
    ) -> None:
        assert self._required(EventPayload.json_schema()) == {
            "slice_id",
            "repo",
            "issue",
            "ts",
            "standing",
            "rounds",
            "spend",
            "budget_usd",
        }

    def test_the_activity_schema_requires_the_coordinates_the_actor_the_tool_and_the_target(self) -> None:
        assert self._required(ActivityPayload.json_schema()) == {
            "ts",
            "repo",
            "issue",
            "slice_id",
            "actor",
            "tool",
            "target",
        }

    def test_none_of_the_nine_schemas_leaves_a_reference_unresolved(self) -> None:
        for payload in (
            HarnessCallPayload,
            CallSpendPayload,
            MetricsEntryPayload,
            CorpusVerdictPayload,
            CorpusDiffPayload,
            DebtPayload,
            CallToolUsePayload,
            UnrecordedCallToolUsePayload,
            EventPayload,
        ):
            emitted = json.dumps(payload.json_schema())

            assert "$ref" not in emitted
            assert "$defs" not in emitted

    @staticmethod
    def _required(schema: dict[str, object]) -> set[str]:
        required = schema["required"]
        assert isinstance(required, list)
        assert all(isinstance(field, str) for field in required)

        return set(required)
