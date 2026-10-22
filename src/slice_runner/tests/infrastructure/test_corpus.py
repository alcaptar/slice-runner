from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.budgets import Budgets
from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.corpus import JudgedRound
from slice_runner.domain.diff_stats import DiffStats
from slice_runner.domain.exceptions import UnreadableCorpusError
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.infrastructure import local_corpus
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.cli import Cli
from slice_runner.infrastructure.corpus_diff_payload import CorpusDiffPayload
from slice_runner.infrastructure.corpus_verdict_payload import CorpusVerdictPayload
from slice_runner.infrastructure.durable_ledger import DurableLedger
from slice_runner.infrastructure.exit_code import ExitCode
from slice_runner.infrastructure.local_corpus import LocalCorpus
from slice_runner.tests.durable_store_home import WithTheDurableStoresOutOfTheRealHome
from slice_runner.tests.infrastructure.stub_ledger import WiredStubLedgers
from slice_runner.tests.mothers.corpus_entry_mother import CorpusEntryMother
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother, JudgeVerdictMother
from slice_runner.tests.mothers.verdict_mother import FindingMother, PriorFindingRulingMother, VerdictMother
from slice_runner.tests.mothers.verification_mother import SliceDiffMother
from slice_runner.tests.mothers.verify_process_mother import VerifyProcessMother

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.tests.doubles import AnsweringByArgv

_STAMP = WithTheDurableStoresOutOfTheRealHome.STAMP


class WrittenCorpus:
    @staticmethod
    def verdicts_under(root: Path) -> list[dict[str, object]]:
        ledger = root / "slice-runner" / "runs" / "verdicts.jsonl"

        return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]

    @staticmethod
    def diffs_under(root: Path) -> list[dict[str, object]]:
        ledger = root / "slice-runner" / "runs" / "diffs.jsonl"

        return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]


class TestTheRecordThatIsWritten(WithTheDurableStoresOutOfTheRealHome):
    def test_a_verification_is_written_as_the_run_it_came_from_and_the_verdict_the_judge_gave(
        self, tmp_path: Path
    ) -> None:
        LocalCorpus(clock=self.frozen_at()).record(CorpusEntryMother.of_the_slice())

        assert WrittenCorpus.verdicts_under(tmp_path) == [
            {
                "repo": CorpusEntryMother.REPO,
                "issue": CorpusEntryMother.ISSUE,
                "slice_id": CorpusEntryMother.SLICE_ID,
                "verify_round": CorpusEntryMother.VERIFY_ROUND,
                "session": CorpusEntryMother.SESSION,
                "verdict": {"ruling": "PASS", "findings": [], "prior_rulings": []},
                "severity_counts": {"high": 0, "medium": 0, "low": 0},
                "diff_stats": {
                    "files_changed": SliceDiffMother.STATS.files_changed,
                    "lines_added": SliceDiffMother.STATS.lines_added,
                    "lines_deleted": SliceDiffMother.STATS.lines_deleted,
                },
                "prior_findings_given": CorpusEntryMother.PRIOR_FINDINGS_GIVEN,
                "diff_fingerprint": SliceDiffMother.of_the_slice().fingerprint,
                "ts": _STAMP.isoformat(),
            }
        ]

    def test_the_diff_is_written_apart_next_to_the_identity_that_ties_it_back_to_its_verdict(
        self, tmp_path: Path
    ) -> None:
        LocalCorpus(clock=self.frozen_at()).record(CorpusEntryMother.of_the_slice())

        assert WrittenCorpus.diffs_under(tmp_path) == [
            {
                "slice_id": CorpusEntryMother.SLICE_ID,
                "diff": SliceDiffMother.TEXT,
                "repo": CorpusEntryMother.REPO,
                "issue": CorpusEntryMother.ISSUE,
                "verify_round": CorpusEntryMother.VERIFY_ROUND,
                "session": CorpusEntryMother.SESSION,
                "ts": _STAMP.isoformat(),
            }
        ]

    def test_the_count_by_severity_travels_written_down_so_nobody_downstream_recounts_the_findings(
        self, tmp_path: Path
    ) -> None:
        vetoed = VerdictMother.failing(
            FindingMother.without_line(),
            FindingMother.without_line(path="src/y.py"),
            FindingMother.with_line(),
        )

        LocalCorpus(clock=self.frozen_at()).record(CorpusEntryMother.of_the_slice(verdict=vetoed))

        assert WrittenCorpus.verdicts_under(tmp_path)[0]["severity_counts"] == {"high": 2, "medium": 1, "low": 0}

    def test_the_pronouncement_on_a_prior_finding_travels_written_down_in_the_verdict_row(self, tmp_path: Path) -> None:
        pronouncing = VerdictMother.pronouncing_on(PriorFindingRulingMother.retired())

        LocalCorpus(clock=self.frozen_at()).record(CorpusEntryMother.of_the_slice(verdict=pronouncing))

        assert WrittenCorpus.verdicts_under(tmp_path)[0]["verdict"] == {
            "ruling": "PASS",
            "findings": [],
            "prior_rulings": [{"id": "f1", "state": "retirado", "reason": "el criterio que citaba ya no existe"}],
        }

    def test_the_number_of_prior_findings_given_to_the_judge_travels_written_down(self, tmp_path: Path) -> None:
        LocalCorpus(clock=self.frozen_at()).record(CorpusEntryMother.of_the_slice(prior_findings_given=3))

        assert WrittenCorpus.verdicts_under(tmp_path)[0]["prior_findings_given"] == 3

    def test_the_size_of_the_diff_travels_written_down_in_the_verdict_row_not_the_diff_row(
        self, tmp_path: Path
    ) -> None:
        stats = DiffStats(files_changed=3, lines_added=40, lines_deleted=12)

        LocalCorpus(clock=self.frozen_at()).record(
            CorpusEntryMother.of_the_slice(diff=SliceDiffMother.of_the_slice(stats=stats))
        )

        assert WrittenCorpus.verdicts_under(tmp_path)[0]["diff_stats"] == {
            "files_changed": stats.files_changed,
            "lines_added": stats.lines_added,
            "lines_deleted": stats.lines_deleted,
        }


class TestTheCorpusOnlyGrows(WithTheDurableStoresOutOfTheRealHome):
    def test_a_second_verification_is_appended_instead_of_overwriting_the_first(self, tmp_path: Path) -> None:
        corpus = LocalCorpus(clock=self.frozen_at())

        corpus.record(CorpusEntryMother.of_the_slice(slice_id="slice-01"))
        corpus.record(CorpusEntryMother.of_the_slice(slice_id="slice-02"))

        assert [record["slice_id"] for record in WrittenCorpus.verdicts_under(tmp_path)] == ["slice-01", "slice-02"]
        assert [record["slice_id"] for record in WrittenCorpus.diffs_under(tmp_path)] == ["slice-01", "slice-02"]

    def test_two_features_that_happen_to_share_a_slice_id_still_keep_their_own_repo_and_issue_apart(
        self, tmp_path: Path
    ) -> None:
        corpus = LocalCorpus(clock=self.frozen_at())

        corpus.record(CorpusEntryMother.of_the_slice(repo="alcaptar/slice-runner", issue=45))
        corpus.record(CorpusEntryMother.of_the_slice(repo="alcaptar/another-feature", issue=99))

        assert [(record["repo"], record["issue"]) for record in WrittenCorpus.verdicts_under(tmp_path)] == [
            ("alcaptar/slice-runner", 45),
            ("alcaptar/another-feature", 99),
        ]


class AskingTheCorpusAboutOneSlice(WithTheDurableStoresOutOfTheRealHome):
    @staticmethod
    def _coordinates() -> SliceCoordinates:
        return SliceCoordinates(
            repo=CorpusEntryMother.REPO,
            issue=CorpusEntryMother.ISSUE,
            slice_id=CanonicalSliceId.of_text(CorpusEntryMother.SLICE_ID),
        )

    @staticmethod
    def _verdict_row_without_diff_stats() -> dict[str, object]:
        return {
            "ts": _STAMP.isoformat(),
            "repo": CorpusEntryMother.REPO,
            "issue": CorpusEntryMother.ISSUE,
            "slice_id": CorpusEntryMother.SLICE_ID,
            "verify_round": CorpusEntryMother.VERIFY_ROUND,
            "session": CorpusEntryMother.SESSION,
            "verdict": {"ruling": "PASS", "findings": []},
            "severity_counts": {"high": 0, "medium": 0, "low": 0},
        }

    @staticmethod
    def _verdict_row_of_a_pass_with_a_medium_finding() -> dict[str, object]:
        return {
            "ts": _STAMP.isoformat(),
            "repo": CorpusEntryMother.REPO,
            "issue": CorpusEntryMother.ISSUE,
            "slice_id": CorpusEntryMother.SLICE_ID,
            "verify_round": CorpusEntryMother.VERIFY_ROUND,
            "session": CorpusEntryMother.SESSION,
            "verdict": {
                "ruling": "PASS",
                "findings": [
                    {
                        "rule": "convenciones",
                        "path": "src/x.py",
                        "severity": "medium",
                        "evidence": "prose in a `.py`",
                        "detail": "the why lives in the pull request body",
                        "line": 42,
                    }
                ],
            },
            "severity_counts": {"high": 0, "medium": 1, "low": 0},
            "diff_stats": {"files_changed": 1, "lines_added": 2, "lines_deleted": 0},
        }

    @staticmethod
    def _verdict_row_written_before_the_pronouncement_existed(*, stats: DiffStats) -> dict[str, object]:
        return {
            "ts": _STAMP.isoformat(),
            "repo": CorpusEntryMother.REPO,
            "issue": CorpusEntryMother.ISSUE,
            "slice_id": CorpusEntryMother.SLICE_ID,
            "verify_round": CorpusEntryMother.VERIFY_ROUND,
            "session": CorpusEntryMother.SESSION,
            "verdict": {"ruling": "PASS", "findings": []},
            "severity_counts": {"high": 0, "medium": 0, "low": 0},
            "diff_stats": {
                "files_changed": stats.files_changed,
                "lines_added": stats.lines_added,
                "lines_deleted": stats.lines_deleted,
            },
        }


class TestTheSizeOfTheLastVerification(AskingTheCorpusAboutOneSlice):
    def test_a_slice_with_no_verification_recorded_answers_with_nothing(self) -> None:
        corpus = LocalCorpus(clock=self.frozen_at())

        assert corpus.size_of_the_last_verification(self._coordinates()) is None

    def test_a_single_verification_answers_with_its_own_size(self) -> None:
        corpus = LocalCorpus(clock=self.frozen_at())
        stats = DiffStats(files_changed=3, lines_added=40, lines_deleted=12)

        corpus.record(CorpusEntryMother.of_the_slice(diff=SliceDiffMother.of_the_slice(stats=stats)))

        assert corpus.size_of_the_last_verification(self._coordinates()) == stats

    def test_two_rounds_of_different_sizes_answer_with_the_last_round_and_not_the_first(self) -> None:
        corpus = LocalCorpus(clock=self.frozen_at())
        first = DiffStats(files_changed=1, lines_added=2, lines_deleted=0)
        last = DiffStats(files_changed=9, lines_added=80, lines_deleted=30)

        corpus.record(CorpusEntryMother.of_the_slice(verify_round=1, diff=SliceDiffMother.of_the_slice(stats=first)))
        corpus.record(CorpusEntryMother.of_the_slice(verify_round=2, diff=SliceDiffMother.of_the_slice(stats=last)))

        assert corpus.size_of_the_last_verification(self._coordinates()) == last

    def test_after_a_reset_the_size_is_the_last_one_written_and_not_the_highest_round_of_the_abandoned_attempt(
        self,
    ) -> None:
        corpus = LocalCorpus(clock=self.frozen_at())
        abandoned = DiffStats(files_changed=9, lines_added=80, lines_deleted=30)
        after_the_reset = DiffStats(files_changed=1, lines_added=2, lines_deleted=0)

        corpus.record(
            CorpusEntryMother.of_the_slice(verify_round=3, diff=SliceDiffMother.of_the_slice(stats=abandoned))
        )
        corpus.record(
            CorpusEntryMother.of_the_slice(verify_round=1, diff=SliceDiffMother.of_the_slice(stats=after_the_reset))
        )

        assert corpus.size_of_the_last_verification(self._coordinates()) == after_the_reset

    def test_a_verification_of_a_different_slice_is_left_out(self) -> None:
        corpus = LocalCorpus(clock=self.frozen_at())
        stats = DiffStats(files_changed=3, lines_added=40, lines_deleted=12)

        corpus.record(
            CorpusEntryMother.of_the_slice(slice_id="slice-99", diff=SliceDiffMother.of_the_slice(stats=stats))
        )

        assert corpus.size_of_the_last_verification(self._coordinates()) is None


class TestTheFingerprintOfTheLastVerification(AskingTheCorpusAboutOneSlice):
    def test_a_slice_with_no_verification_recorded_answers_with_nothing(self) -> None:
        corpus = LocalCorpus(clock=self.frozen_at())

        assert corpus.fingerprint_of_the_last_verification(self._coordinates()) is None

    def test_two_rounds_answer_with_the_fingerprint_of_the_diff_of_the_last_one(self) -> None:
        corpus = LocalCorpus(clock=self.frozen_at())
        first = SliceDiffMother.of_the_slice(text="first")
        last = SliceDiffMother.of_the_slice(text="last")

        corpus.record(CorpusEntryMother.of_the_slice(verify_round=1, diff=first))
        corpus.record(CorpusEntryMother.of_the_slice(verify_round=2, diff=last))

        assert corpus.fingerprint_of_the_last_verification(self._coordinates()) == last.fingerprint

    def test_two_diffs_that_differ_in_one_byte_have_different_fingerprints(self) -> None:
        corpus = LocalCorpus(clock=self.frozen_at())
        corpus.record(CorpusEntryMother.of_the_slice(diff=SliceDiffMother.of_the_slice(text="return 2\n")))

        assert corpus.fingerprint_of_the_last_verification(self._coordinates()) != (
            SliceDiffMother.of_the_slice(text="return 3\n").fingerprint
        )

    def test_a_verification_of_a_different_slice_is_left_out(self) -> None:
        corpus = LocalCorpus(clock=self.frozen_at())

        corpus.record(CorpusEntryMother.of_the_slice(slice_id="slice-99"))

        assert corpus.fingerprint_of_the_last_verification(self._coordinates()) is None

    def test_a_row_written_before_the_fingerprint_existed_has_nothing_to_compare_with(self, tmp_path: Path) -> None:
        stats = DiffStats(files_changed=3, lines_added=40, lines_deleted=12)
        ledger = tmp_path / "slice-runner" / "runs" / "verdicts.jsonl"
        ledger.parent.mkdir(parents=True)
        row = self._verdict_row_written_before_the_pronouncement_existed(stats=stats)
        ledger.write_text(json.dumps(row) + "\n", encoding="utf-8")

        assert LocalCorpus(clock=self.frozen_at()).fingerprint_of_the_last_verification(self._coordinates()) is None

    def test_answering_it_never_needs_to_load_the_heavy_diff_ledger(self, tmp_path: Path) -> None:
        corpus = LocalCorpus(clock=self.frozen_at())
        corpus.record(CorpusEntryMother.of_the_slice())
        (tmp_path / "slice-runner" / "runs" / "diffs.jsonl").write_text("not json\n", encoding="utf-8")

        assert (
            corpus.fingerprint_of_the_last_verification(self._coordinates())
            == SliceDiffMother.of_the_slice().fingerprint
        )


class TestTheRoundsOfTheSlice(AskingTheCorpusAboutOneSlice):
    def test_a_slice_with_no_verification_recorded_answers_with_no_rounds(self) -> None:
        corpus = LocalCorpus(clock=self.frozen_at())

        assert corpus.rounds_of_the_slice(self._coordinates()) == ()

    def test_two_rounds_recorded_answer_both_numbered_by_their_own_verify_round(self) -> None:
        corpus = LocalCorpus(clock=self.frozen_at())
        first = VerdictMother.failing(FindingMother.without_line(rule="regla-uno"))
        second = VerdictMother.failing(FindingMother.without_line(rule="regla-dos"))

        corpus.record(CorpusEntryMother.of_the_slice(verify_round=1, verdict=first))
        corpus.record(CorpusEntryMother.of_the_slice(verify_round=2, verdict=second))

        assert corpus.rounds_of_the_slice(self._coordinates()) == (
            JudgedRound(round=1, findings=first.findings),
            JudgedRound(round=2, findings=second.findings),
        )

    def test_a_verification_of_a_different_slice_is_left_out(self) -> None:
        corpus = LocalCorpus(clock=self.frozen_at())

        corpus.record(CorpusEntryMother.of_the_slice(slice_id="slice-99"))

        assert corpus.rounds_of_the_slice(self._coordinates()) == ()

    def test_two_rows_written_for_the_same_round_count_once_as_the_last_one_written(self) -> None:
        corpus = LocalCorpus(clock=self.frozen_at())
        discarded = VerdictMother.failing(FindingMother.without_line(rule="descartado"))
        kept = VerdictMother.failing(FindingMother.without_line(rule="definitivo"))

        corpus.record(CorpusEntryMother.of_the_slice(verify_round=1, verdict=discarded))
        corpus.record(CorpusEntryMother.of_the_slice(verify_round=1, verdict=kept))

        assert corpus.rounds_of_the_slice(self._coordinates()) == (JudgedRound(round=1, findings=kept.findings),)


class TestTheRoundsWrittenWithThePreviousScale(AskingTheCorpusAboutOneSlice):
    def test_a_pass_with_a_medium_finding_is_still_read_back_with_that_finding(self, tmp_path: Path) -> None:
        ledger = tmp_path / "slice-runner" / "runs" / "verdicts.jsonl"
        ledger.parent.mkdir(parents=True)
        ledger.write_text(json.dumps(self._verdict_row_of_a_pass_with_a_medium_finding()) + "\n", encoding="utf-8")

        rounds = LocalCorpus(clock=self.frozen_at()).rounds_of_the_slice(self._coordinates())

        assert rounds == (JudgedRound(round=CorpusEntryMother.VERIFY_ROUND, findings=(FindingMother.with_line(),)),)


class TestTheHeavyDiffStaysOutOfTheVerdictLedger(AskingTheCorpusAboutOneSlice):
    def test_counting_findings_never_needs_to_load_the_diff_of_any_verdict(self, tmp_path: Path) -> None:
        LocalCorpus(clock=self.frozen_at()).record(CorpusEntryMother.of_the_slice())

        for record in WrittenCorpus.verdicts_under(tmp_path):
            assert "diff" not in record

    def test_answering_the_size_of_a_slice_never_needs_to_load_the_heavy_diff_ledger(self, tmp_path: Path) -> None:
        stats = DiffStats(files_changed=3, lines_added=40, lines_deleted=12)
        corpus = LocalCorpus(clock=self.frozen_at())
        corpus.record(CorpusEntryMother.of_the_slice(diff=SliceDiffMother.of_the_slice(stats=stats)))
        diffs_ledger = tmp_path / "slice-runner" / "runs" / "diffs.jsonl"
        diffs_ledger.write_text("not json\n", encoding="utf-8")

        assert corpus.size_of_the_last_verification(self._coordinates()) == stats

    def test_a_row_the_program_wrote_before_the_schema_changed_does_not_kill_a_closure_whose_last_row_is_readable(
        self, tmp_path: Path
    ) -> None:
        stats = DiffStats(files_changed=3, lines_added=40, lines_deleted=12)
        corpus = LocalCorpus(clock=self.frozen_at())
        corpus.record(CorpusEntryMother.of_the_slice(diff=SliceDiffMother.of_the_slice(stats=stats)))
        ledger = tmp_path / "slice-runner" / "runs" / "verdicts.jsonl"
        earlier = self._verdict_row_without_diff_stats()
        ledger.write_text(json.dumps(earlier) + "\n" + ledger.read_text(encoding="utf-8"), encoding="utf-8")

        assert corpus.size_of_the_last_verification(self._coordinates()) == stats

    def test_a_verdict_row_from_before_the_size_moved_in_is_rejected_instead_of_read_without_it(
        self, tmp_path: Path
    ) -> None:
        ledger = tmp_path / "slice-runner" / "runs" / "verdicts.jsonl"
        ledger.parent.mkdir(parents=True)
        without_diff_stats = self._verdict_row_without_diff_stats()
        ledger.write_text(json.dumps(without_diff_stats) + "\n", encoding="utf-8")

        with pytest.raises(UnreadableCorpusError, match="generation"):
            LocalCorpus(clock=self.frozen_at()).size_of_the_last_verification(self._coordinates())

    def test_a_row_written_before_the_pronouncement_existed_is_still_read_without_it(self) -> None:
        stats = DiffStats(files_changed=3, lines_added=40, lines_deleted=12)
        row = self._verdict_row_written_before_the_pronouncement_existed(stats=stats)

        read = CorpusVerdictPayload.from_dict(row)

        assert read.verdict.prior_rulings == []
        assert read.prior_findings_given is None


class TestWhereTheCorpusLives:
    def test_the_directory_is_created_when_it_is_not_there_so_the_first_pair_is_not_lost(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path / "never-used-before"))

        LocalCorpus(clock=WithTheDurableStoresOutOfTheRealHome.frozen_at()).record(CorpusEntryMother.of_the_slice())

        assert (tmp_path / "never-used-before" / "slice-runner" / "runs" / "verdicts.jsonl").exists()
        assert (tmp_path / "never-used-before" / "slice-runner" / "runs" / "diffs.jsonl").exists()

    def test_without_the_variable_it_falls_back_to_the_home_of_the_tool_and_expands_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(ClaudeConfig.VARIABLE, raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))

        LocalCorpus(clock=WithTheDurableStoresOutOfTheRealHome.frozen_at()).record(CorpusEntryMother.of_the_slice())

        assert (tmp_path / ".claude" / "slice-runner" / "runs" / "verdicts.jsonl").exists()

    def test_the_ledger_paths_are_composed_under_runs_and_not_under_the_retired_log_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

        verdicts = DurableLedger(name=LocalCorpus.LEDGER, row=CorpusVerdictPayload).path()
        diffs = DurableLedger(name=LocalCorpus.DIFF_LEDGER, row=CorpusDiffPayload).path()

        assert verdicts == tmp_path / "slice-runner" / "runs" / "verdicts.jsonl"
        assert diffs == tmp_path / "slice-runner" / "runs" / "diffs.jsonl"


class TestTheAdapterOwnsOnlyItsNameAndItsPayload:
    def test_recording_a_verification_reaches_only_the_two_ledgers_and_writes_no_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))
        created = WiredStubLedgers.on(local_corpus, monkeypatch)

        LocalCorpus(clock=WithTheDurableStoresOutOfTheRealHome.frozen_at()).record(CorpusEntryMother.of_the_slice())

        assert [(stub.name, stub.row) for stub in created] == [
            (LocalCorpus.LEDGER, CorpusVerdictPayload),
            (LocalCorpus.DIFF_LEDGER, CorpusDiffPayload),
        ]
        assert [len(stub.appended) for stub in created] == [1, 1]
        assert not (tmp_path / "slice-runner").exists()


class TestNothingOfTheCorpusCanReachAPullRequest(WithTheDurableStoresOutOfTheRealHome):
    @staticmethod
    def _verified(worktree: Path) -> AnsweringByArgv:
        process = VerifyProcessMother.judging(
            HarnessEnvelopeMother.carrying(JudgeVerdictMother.passing()), worktree=str(worktree)
        )

        code = Cli(process=process, budgets=Budgets()).verify(
            repo=str(worktree), base=VerifyProcessMother.BASE, slice_id=CorpusEntryMother.SLICE_ID
        )

        assert code == ExitCode.OK

        return process

    @staticmethod
    def _worktree(tmp_path: Path) -> Path:
        worktree = tmp_path / "repo"
        worktree.mkdir()

        return worktree

    def test_a_verification_asks_git_only_for_reads_so_it_leaves_the_tree_of_the_repo_as_it_found_it(
        self, tmp_path: Path
    ) -> None:
        process = self._verified(self._worktree(tmp_path))

        git_subcommands = {call.argv[3] for call in process.calls if call.argv[0] == "git"}
        assert git_subcommands == {"diff"}

    def test_the_pair_lands_outside_the_repo_where_no_git_add_of_the_slice_can_sweep_it_in(
        self, tmp_path: Path
    ) -> None:
        worktree = self._worktree(tmp_path)

        self._verified(worktree)

        assert len(WrittenCorpus.verdicts_under(tmp_path)) == 1
        assert len(WrittenCorpus.diffs_under(tmp_path)) == 1
        assert list(worktree.rglob("verdicts.jsonl")) == []
        assert list(worktree.rglob("diffs.jsonl")) == []
