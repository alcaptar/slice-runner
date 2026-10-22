from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

from slice_runner.application.actions.record_closure import RecordClosure, RecordClosureParams
from slice_runner.domain.budgets import Budgets
from slice_runner.domain.call_spend_log import CallSpendLog
from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.closing_reason import ClosingReason
from slice_runner.domain.closure import Closure
from slice_runner.domain.corpus import Corpus
from slice_runner.domain.debt_ledger import DebtDeclaration, DebtLedger
from slice_runner.domain.declared_debt import DeclaredDebt
from slice_runner.domain.diff_stats import DiffStats
from slice_runner.domain.effort import Effort
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.metrics_log import MetricsLog
from slice_runner.domain.role_models import RoleModels
from slice_runner.domain.run_repository import RunRepository
from slice_runner.domain.severity import Severity
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.tests.mothers.discarded_call_mother import DiscardedCallMother
from slice_runner.tests.mothers.findings_history_mother import FindingsHistoryMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.judged_round_mother import JudgedRoundMother
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.verdict_mother import FindingMother

if TYPE_CHECKING:
    from slice_runner.domain.closed_slice import ClosedSlice

_REPO = "alcaptar/slice-runner"
_ISSUE = 38
_SLICE = "slice-07"
_NAME = "una-llamada-una-fila"
_COORDINATES = SliceCoordinates(repo=_REPO, issue=_ISSUE, slice_id=CanonicalSliceId.of_text(_SLICE))


class _Closer:
    def __init__(self) -> None:
        self.metrics: Mock = create_autospec(MetricsLog, spec_set=True, instance=True)
        self.repository: Mock = create_autospec(RunRepository, spec_set=True, instance=True)
        self.spend_log: Mock = create_autospec(CallSpendLog, spec_set=True, instance=True)
        self.spend_log.spend_of_the_slice.return_value = HarnessSpend.nothing()
        self.corpus: Mock = create_autospec(Corpus, spec_set=True, instance=True)
        self.corpus.size_of_the_last_verification.return_value = None
        self.corpus.rounds_of_the_slice.return_value = ()
        self.debt_ledger: Mock = create_autospec(DebtLedger, spec_set=True, instance=True)
        self.debt_ledger.declarations_of_the_slice.return_value = ()

    @property
    def action(self) -> RecordClosure:
        return RecordClosure(
            metrics=self.metrics,
            repository=self.repository,
            spend_log=self.spend_log,
            corpus=self.corpus,
            debt_ledger=self.debt_ledger,
        )

    def close(self, **overrides: object) -> ClosedSlice:
        params = {
            "repo": _REPO,
            "issue": _ISSUE,
            "slice_id": _SLICE,
            "name": _NAME,
            "closure": Closure.merged(),
            "run": RunMother.awaiting_merge(),
            "budgets": Budgets(),
            "models": RoleModels(
                implement="sonnet", verify="sonnet", implement_effort=Effort.HIGH, verify_effort=Effort.HIGH
            ),
            **overrides,
        }
        self.action.execute(RecordClosureParams(**params))  # type: ignore[arg-type]
        written: ClosedSlice = self.metrics.record.call_args.args[0]

        return written


class TestTheRowItWrites:
    def test_the_row_names_the_slice_and_the_state_the_run_closed_in(self) -> None:
        closer = _Closer()

        written = closer.close(closure=Closure.because_of(ClosingReason.JUDGE))

        assert written.repo == _REPO
        assert written.slice_id == _SLICE
        assert written.name == _NAME
        assert written.closure == Closure.because_of(ClosingReason.JUDGE)

    def test_the_findings_of_every_round_and_of_the_last_one_travel_apart_so_a_fixed_one_is_not_lost(self) -> None:
        closer = _Closer()
        closer.corpus.rounds_of_the_slice.return_value = (
            JudgedRoundMother.of_the_round(1, FindingMother.without_line()),
            JudgedRoundMother.of_the_round(2, FindingMother.low_severity()),
        )

        written = closer.close()

        assert written.count_findings(Severity.HIGH) == 1
        assert written.count_findings_of_the_last_round(Severity.HIGH) == 0

    def test_the_cause_of_a_discarded_verdict_reaches_the_row(self) -> None:
        closer = _Closer()
        discarded = DiscardedCallMother.of_an_incoherent_verdict()

        written = closer.close(run=RunMother.awaiting_merge_after_discarding(discarded))

        assert written.run.discarded_call == discarded

    def test_the_size_of_the_diff_measured_at_the_last_verify_reaches_the_row(self) -> None:
        closer = _Closer()
        stats = DiffStats(files_changed=3, lines_added=40, lines_deleted=12)
        closer.corpus.size_of_the_last_verification.return_value = stats

        written = closer.close()

        assert written.diff_stats == stats

    def test_a_closure_with_no_verification_recorded_for_the_slice_carries_no_diff_stats_instead_of_a_zero_one(
        self,
    ) -> None:
        closer = _Closer()

        written = closer.close()

        assert written.diff_stats is None

    def test_the_size_is_asked_from_the_corpus_and_not_from_a_parameter_carried_in_memory(self) -> None:
        closer = _Closer()

        closer.close()

        closer.corpus.size_of_the_last_verification.assert_called_once_with(_COORDINATES)

    def test_the_budgets_the_run_was_conducted_with_reach_the_row(self) -> None:
        closer = _Closer()
        budgets = Budgets(slice_cost_usd=12.5)

        written = closer.close(budgets=budgets)

        assert written.budgets == budgets

    def test_the_model_assigned_to_each_role_reaches_the_row(self) -> None:
        closer = _Closer()
        models = RoleModels(implement="opus", verify="haiku", implement_effort=Effort.HIGH, verify_effort=Effort.HIGH)

        written = closer.close(models=models)

        assert written.models == models


class TestFindingsComeFromTheCorpus:
    def test_a_closure_whose_invocation_verified_nothing_still_carries_what_the_corpus_already_had(self) -> None:
        closer = _Closer()
        closer.corpus.rounds_of_the_slice.return_value = (
            JudgedRoundMother.of_the_round(1, FindingMother.without_line()),
        )

        written = closer.close()

        assert written.count_findings(Severity.HIGH) == 1

    def test_two_invocations_worth_of_rounds_in_the_corpus_sum_instead_of_only_the_last_one(self) -> None:
        closer = _Closer()
        first_invocation = FindingMother.without_line(rule="regla-uno")
        second_invocation = FindingMother.without_line(rule="regla-dos", path="src/y.py")
        closer.corpus.rounds_of_the_slice.return_value = (
            JudgedRoundMother.of_the_round(1, first_invocation),
            JudgedRoundMother.of_the_round(2, second_invocation),
        )

        written = closer.close()

        assert written.count_findings(Severity.HIGH) == 2

    def test_the_last_round_that_travels_is_the_one_with_the_highest_verify_round_not_the_tuple_order(self) -> None:
        closer = _Closer()
        earlier = FindingMother.without_line(rule="regla-uno")
        later = FindingMother.without_line(rule="regla-dos", path="src/y.py")
        closer.corpus.rounds_of_the_slice.return_value = (
            JudgedRoundMother.of_the_round(5, later),
            JudgedRoundMother.of_the_round(4, earlier),
        )

        written = closer.close()

        assert written.findings_of_the_last_round == (later,)

    def test_the_reading_is_asked_from_the_corpus_port_and_not_from_a_field_carried_in_memory(self) -> None:
        closer = _Closer()

        closer.close()

        closer.corpus.rounds_of_the_slice.assert_called_once_with(_COORDINATES)


class TestWhichSpendsCount:
    def test_the_row_asks_the_spend_log_for_this_slice_and_writes_what_it_answers(self) -> None:
        closer = _Closer()
        closer.spend_log.spend_of_the_slice.return_value = HarnessSpendMother.of_the_implementer_call()

        written = closer.close()

        closer.spend_log.spend_of_the_slice.assert_called_once_with(_COORDINATES)
        assert written.spend == HarnessSpendMother.of_the_implementer_call()

    def test_the_spend_the_persisted_run_already_carries_is_not_added_on_top_of_what_the_slice_answers(self) -> None:
        closer = _Closer()
        already_on_the_run = HarnessSpendMother.of_the_understanding_call()
        closer.spend_log.spend_of_the_slice.return_value = HarnessSpend.summing(
            (HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call())
        )

        written = closer.close(run=RunMother.judging_after_spending(already_on_the_run))

        assert written.spend == HarnessSpend.summing(
            (HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call())
        )

    def test_a_spend_log_with_nothing_measured_leaves_the_row_with_no_spend_instead_of_a_zero_one(self) -> None:
        closer = _Closer()

        written = closer.close()

        assert written.spends == ()

    def test_a_call_that_cost_nothing_but_was_measured_still_reaches_the_row_instead_of_being_treated_as_unmeasured(
        self,
    ) -> None:
        closer = _Closer()
        free_call = HarnessSpendMother.of_a_call_that_cost_nothing()
        closer.spend_log.spend_of_the_slice.return_value = free_call

        written = closer.close()

        assert written.spends == (free_call,)


class TestPublishingTheCatchUpConflict:
    def test_a_closure_by_conflict_with_paths_publishes_them(self) -> None:
        closer = _Closer()
        paths = ("shared.txt", "src/module.py")

        closer.close(closure=Closure.because_of(ClosingReason.CI_CONFLICT), conflicting_paths=paths)

        closer.repository.publish_catch_up_conflict.assert_called_once_with(repo=_REPO, issue=_ISSUE, paths=paths)

    def test_a_closure_by_conflict_with_no_paths_publishes_nothing(self) -> None:
        closer = _Closer()

        closer.close(closure=Closure.because_of(ClosingReason.CI_CONFLICT), conflicting_paths=())

        closer.repository.publish_catch_up_conflict.assert_not_called()

    def test_a_closure_in_another_state_never_publishes_even_if_conflicting_paths_arrived(self) -> None:
        closer = _Closer()

        closer.close(closure=Closure.merged(), conflicting_paths=("shared.txt",))

        closer.repository.publish_catch_up_conflict.assert_not_called()


class TestPublishingTheVetoFindings:
    def test_a_closure_by_veto_with_findings_publishes_the_whole_history(self) -> None:
        closer = _Closer()
        high = FindingMother.without_line()
        low = FindingMother.low_severity()
        closer.corpus.rounds_of_the_slice.return_value = (JudgedRoundMother.of_the_round(1, high, low),)

        closer.close(closure=Closure.because_of(ClosingReason.JUDGE))

        closer.repository.publish_findings.assert_called_once_with(
            repo=_REPO,
            issue=_ISSUE,
            history=FindingsHistoryMother.of_a_single_round(high, low),
            debt=DeclaredDebt.nothing(),
        )

    def test_a_closure_by_an_unchanged_diff_publishes_the_history_just_like_a_veto(self) -> None:
        closer = _Closer()
        high = FindingMother.without_line()
        closer.corpus.rounds_of_the_slice.return_value = (JudgedRoundMother.of_the_round(1, high),)

        closer.close(closure=Closure.because_of(ClosingReason.JUDGE))

        closer.repository.publish_findings.assert_called_once_with(
            repo=_REPO,
            issue=_ISSUE,
            history=FindingsHistoryMother.of_a_single_round(high),
            debt=DeclaredDebt.nothing(),
        )

    def test_what_the_implementer_declared_left_out_is_published_next_to_what_the_judge_still_demands(self) -> None:
        closer = _Closer()
        closer.corpus.rounds_of_the_slice.return_value = (
            JudgedRoundMother.of_the_round(1, FindingMother.without_line()),
        )
        closer.debt_ledger.declarations_of_the_slice.return_value = (
            DebtDeclaration(left_out=("no cubri el caso de un binario",)),
        )

        closer.close(closure=Closure.because_of(ClosingReason.JUDGE))

        published = closer.repository.publish_findings.call_args.kwargs["debt"]
        assert published.left_out == ("no cubri el caso de un binario",)

    def test_a_closure_by_veto_with_no_findings_at_all_publishes_nothing(self) -> None:
        closer = _Closer()

        closer.close(closure=Closure.because_of(ClosingReason.JUDGE))

        closer.repository.publish_findings.assert_not_called()

    def test_a_closure_in_another_state_never_publishes_even_if_findings_arrived(self) -> None:
        closer = _Closer()
        closer.corpus.rounds_of_the_slice.return_value = (
            JudgedRoundMother.of_the_round(1, FindingMother.without_line()),
        )

        closer.close(closure=Closure.merged())

        closer.repository.publish_findings.assert_not_called()


class TestTheDebtThatReachesTheRow:
    def test_what_the_ledger_holds_reaches_the_row_and_not_a_debt_carried_by_the_params(self) -> None:
        closer = _Closer()
        closer.debt_ledger.declarations_of_the_slice.return_value = (
            DebtDeclaration(left_out=("no cubri el caso de un binario",)),
        )

        written = closer.close()

        assert written.debt.left_out == ("no cubri el caso de un binario",)

    def test_a_closure_whose_invocation_implemented_nothing_still_closes_with_what_the_ledger_already_had(
        self,
    ) -> None:
        closer = _Closer()
        closer.debt_ledger.declarations_of_the_slice.return_value = (
            DebtDeclaration(left_out=("no cubri el caso de un binario",)),
        )

        written = closer.close()

        assert (written.debt.declared, written.debt.left_out) == (True, ("no cubri el caso de un binario",))

    def test_two_rounds_that_declared_different_gaps_both_reach_the_row(self) -> None:
        closer = _Closer()
        closer.debt_ledger.declarations_of_the_slice.return_value = (
            DebtDeclaration(left_out=("no cubri el caso de un binario",)),
            DebtDeclaration(left_out=("falta el caso de rename",)),
        )

        written = closer.close()

        assert written.debt.left_out == ("no cubri el caso de un binario", "falta el caso de rename")

    def test_a_declaration_that_explicitly_left_nothing_out_writes_declared_debt_with_no_items(self) -> None:
        closer = _Closer()
        closer.debt_ledger.declarations_of_the_slice.return_value = (DebtDeclaration(left_out=()),)

        written = closer.close()

        assert (written.debt.declared, written.debt.left_out) == (True, ())

    def test_a_slice_whose_declaration_was_never_written_closes_with_nothing_declared(self) -> None:
        closer = _Closer()

        written = closer.close()

        assert (written.debt.declared, written.debt.left_out) == (False, ())

    def test_the_debt_is_asked_from_the_ledger_and_not_from_a_field_carried_in_memory(self) -> None:
        closer = _Closer()

        closer.close()

        closer.debt_ledger.declarations_of_the_slice.assert_called_once_with(_COORDINATES)
