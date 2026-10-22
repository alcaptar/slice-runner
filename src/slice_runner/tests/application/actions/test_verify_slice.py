from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.verify_slice import VerifySlice, VerifySliceParams
from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.corpus import Corpus
from slice_runner.domain.diff_reader import DiffReader
from slice_runner.domain.exceptions import DiffNotReadableError, UnchangedDiffError
from slice_runner.domain.skill_library import SkillLibrary
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.domain.verifier import Verifier
from slice_runner.tests.mothers.design_captures_mother import DesignCapturesMother
from slice_runner.tests.mothers.design_mother import DesignMother
from slice_runner.tests.mothers.verdict_mother import FindingMother, VerdictMother
from slice_runner.tests.mothers.verification_mother import (
    JudgeMother,
    SliceDiffMother,
    SliceUnderReviewMother,
    VerificationMother,
    VerifySliceParamsMother,
)

if TYPE_CHECKING:
    from slice_runner.domain.corpus_entry import CorpusEntry
    from slice_runner.domain.judge import Judge
    from slice_runner.domain.slice_under_review import SliceUnderReview

_DIFF = SliceDiffMother.of_the_slice(files=("src/a.py", "src/tests/test_a.py"))

_PARAMS = VerifySliceParamsMother.against_the_base()

_YARDSTICK = (Path("/toolbox/skills"), Path("/toolbox/plugins"))


class TestVerifySlice:
    @pytest.fixture
    def reader(self) -> Mock:
        reader: Mock = create_autospec(DiffReader, spec_set=True, instance=True)
        reader.read.return_value = _DIFF
        return reader

    @pytest.fixture
    def verifier(self) -> Mock:
        verifier: Mock = create_autospec(Verifier, spec_set=True, instance=True)
        verifier.verify.return_value = VerificationMother.passing()
        return verifier

    @pytest.fixture
    def skills(self) -> Mock:
        skills: Mock = create_autospec(SkillLibrary, spec_set=True, instance=True)
        skills.directories.return_value = _YARDSTICK
        return skills

    @pytest.fixture
    def judge(self) -> Judge:
        return JudgeMother.adversarial()

    @pytest.fixture
    def corpus(self) -> Mock:
        corpus: Mock = create_autospec(Corpus, spec_set=True, instance=True)
        return corpus

    @pytest.fixture
    def action(self, reader: Mock, verifier: Mock, judge: Judge, skills: Mock, corpus: Mock) -> VerifySlice:
        return VerifySlice(reader=reader, verifier=verifier, judge=judge, skills=skills, corpus=corpus)

    @staticmethod
    def _recorded(corpus: Mock) -> CorpusEntry:
        entry: CorpusEntry = corpus.record.call_args.args[0]
        return entry

    @staticmethod
    def _judged_by(verifier: Mock) -> Judge:
        judge: Judge = verifier.verify.call_args.args[0]
        return judge

    @staticmethod
    def _reviewed(verifier: Mock) -> SliceUnderReview:
        review: SliceUnderReview = verifier.verify.call_args.args[1]
        return review

    def test_the_diff_is_read_for_the_worktree_and_base_that_were_asked_for(
        self, action: VerifySlice, reader: Mock
    ) -> None:
        action.execute(_PARAMS)

        reader.read.assert_called_once_with(worktree=_PARAMS.worktree, base=_PARAMS.base)

    def test_the_judge_gets_the_diff_that_was_just_read_and_not_the_repo_and_base(
        self, action: VerifySlice, verifier: Mock
    ) -> None:
        action.execute(_PARAMS)

        assert self._reviewed(verifier).diff is _DIFF

    def test_what_the_judge_may_read_is_decided_here_and_is_the_worktree_plus_the_yardstick(
        self, action: VerifySlice, verifier: Mock
    ) -> None:
        action.execute(_PARAMS)

        assert self._judged_by(verifier).readable == (Path(_PARAMS.worktree), *_YARDSTICK)

    def test_the_injected_judge_is_left_untouched_so_one_run_cannot_widen_the_next(
        self, action: VerifySlice, judge: Judge
    ) -> None:
        action.execute(_PARAMS)
        action.execute(_PARAMS)

        assert judge.readable == ()

    def test_the_judge_keeps_the_rubric_and_the_tools_it_was_built_with(
        self, action: VerifySlice, verifier: Mock
    ) -> None:
        action.execute(_PARAMS)

        judged_by = self._judged_by(verifier)
        assert (judged_by.rubric, judged_by.tools) == (JudgeMother.RUBRIC, JudgeMother.TOOLS)

    def test_the_repo_and_the_issue_travel_as_data_and_not_only_as_something_the_judge_may_read(
        self, action: VerifySlice, verifier: Mock
    ) -> None:
        action.execute(_PARAMS)

        reviewed = self._reviewed(verifier)
        assert (reviewed.repo, reviewed.issue) == (_PARAMS.repo, _PARAMS.issue)

    def test_the_slice_and_the_yardstick_its_items_are_measured_against_travel_to_the_judge_too(
        self, action: VerifySlice, verifier: Mock
    ) -> None:
        action.execute(_PARAMS)

        reviewed = self._reviewed(verifier)
        assert (reviewed.slice_id, reviewed.signal, reviewed.criteria, reviewed.sources, reviewed.checklist) == (
            _PARAMS.slice_id,
            _PARAMS.signal,
            _PARAMS.criteria,
            _PARAMS.sources,
            _PARAMS.checklist,
        )

    def test_what_the_slice_declares_as_excluded_travels_to_the_judge_too(
        self, action: VerifySlice, verifier: Mock
    ) -> None:
        params = replace(_PARAMS, excludes="el panel de grafana que consume esta serie")

        action.execute(params)

        assert self._reviewed(verifier).excludes == params.excludes

    def test_what_the_slice_declares_it_replaces_travels_to_the_judge_too(
        self, action: VerifySlice, verifier: Mock
    ) -> None:
        params = replace(_PARAMS, replaces="si - el adaptador viejo; apagando el flag")

        action.execute(params)

        assert self._reviewed(verifier).replaces == params.replaces

    def test_the_findings_the_previous_round_raised_travel_to_the_judge_too(
        self, action: VerifySlice, verifier: Mock
    ) -> None:
        findings = (FindingMother.with_line(), FindingMother.without_line())
        params = replace(_PARAMS, prior_findings=findings)

        action.execute(params)

        assert self._reviewed(verifier).prior_findings == findings

    def test_what_the_implementer_declared_left_out_travels_to_the_judge_too(
        self, action: VerifySlice, verifier: Mock
    ) -> None:
        debt = SliceUnderReviewMother.two_declared_gaps()
        params = replace(_PARAMS, debt=debt)

        action.execute(params)

        assert self._reviewed(verifier).debt == debt

    def test_the_design_decisions_travel_to_the_judge_too(self, action: VerifySlice, verifier: Mock) -> None:
        decisions = SliceUnderReviewMother.one_decision_of_the_parent_and_one_of_the_subissue()
        params = replace(_PARAMS, decisions=decisions)

        action.execute(params)

        assert self._reviewed(verifier).decisions == decisions

    def test_the_designs_the_slice_cites_travel_to_the_judge_too(self, action: VerifySlice, verifier: Mock) -> None:
        params = replace(_PARAMS, designs=(DesignMother.board(), DesignMother.detail()))

        action.execute(params)

        assert self._reviewed(verifier).designs == (DesignMother.board(), DesignMother.detail())

    def test_the_captures_read_for_the_designs_travel_to_the_judge_too(
        self, action: VerifySlice, verifier: Mock
    ) -> None:
        captures = DesignCapturesMother.of_the_board_and_the_detail()
        params = replace(_PARAMS, designs=(DesignMother.board(), DesignMother.detail()), captures=captures)

        action.execute(params)

        assert self._reviewed(verifier).captures == captures

    def test_captures_declared_missing_travel_to_the_judge_with_their_reason(
        self, action: VerifySlice, verifier: Mock
    ) -> None:
        params = replace(_PARAMS, designs=(DesignMother.board(),), captures=DesignCapturesMother.missing())

        action.execute(params)

        assert self._reviewed(verifier).captures == DesignCapturesMother.missing()

    def test_the_deviations_the_implementer_declared_travel_to_the_judge_too(
        self, action: VerifySlice, verifier: Mock
    ) -> None:
        deviations = SliceUnderReviewMother.two_declared_deviations()
        params = replace(_PARAMS, deviations=deviations)

        action.execute(params)

        assert self._reviewed(verifier).deviations == deviations

    def test_the_verification_comes_back_without_being_reinterpreted(self, action: VerifySlice, verifier: Mock) -> None:
        expected = VerificationMother.failing_after_a_denied_read()
        verifier.verify.return_value = expected

        assert action.execute(_PARAMS) is expected

    def test_every_verification_hands_the_corpus_the_pair_it_just_produced_under_the_slice_that_was_asked_for(
        self, action: VerifySlice, corpus: Mock
    ) -> None:
        action.execute(_PARAMS)

        recorded = self._recorded(corpus)
        assert (recorded.repo, recorded.issue, recorded.slice_id, recorded.diff, recorded.verdict) == (
            _PARAMS.repo,
            _PARAMS.issue,
            _PARAMS.slice_id,
            _DIFF,
            VerdictMother.passing(),
        )

    def test_the_recorded_pair_carries_the_verify_round_that_was_asked_for_and_not_a_reinterpreted_one(
        self, action: VerifySlice, corpus: Mock
    ) -> None:
        params = replace(_PARAMS, verify_round=2)

        action.execute(params)

        assert self._recorded(corpus).verify_round == 2

    def test_the_recorded_pair_carries_the_session_the_verification_came_back_with(
        self, action: VerifySlice, corpus: Mock
    ) -> None:
        action.execute(_PARAMS)

        assert self._recorded(corpus).session == VerificationMother.SESSION

    def test_the_recorded_pair_carries_how_many_prior_findings_the_judge_was_given(
        self, action: VerifySlice, corpus: Mock
    ) -> None:
        findings = (FindingMother.with_line(), FindingMother.without_line())
        params = replace(_PARAMS, prior_findings=findings)

        action.execute(params)

        assert self._recorded(corpus).prior_findings_given == len(findings)

    def test_a_vetoed_verification_is_recorded_too_because_the_corpus_is_not_only_the_clean_pairs(
        self, action: VerifySlice, corpus: Mock, verifier: Mock
    ) -> None:
        vetoed = VerdictMother.failing()
        verifier.verify.return_value = VerificationMother.vetoing(vetoed)

        action.execute(_PARAMS)

        assert self._recorded(corpus).verdict == vetoed

    def test_with_no_diff_to_read_the_judge_is_not_invoked_at_all(
        self, action: VerifySlice, reader: Mock, verifier: Mock
    ) -> None:
        reader.read.side_effect = DiffNotReadableError("nothing staged against master")

        with pytest.raises(DiffNotReadableError):
            action.execute(_PARAMS)

        verifier.verify.assert_not_called()


class TestVerifySliceComparingWithTheLastVerification:
    @pytest.fixture
    def reader(self) -> Mock:
        reader: Mock = create_autospec(DiffReader, spec_set=True, instance=True)
        reader.read.return_value = _DIFF
        return reader

    @pytest.fixture
    def verifier(self) -> Mock:
        verifier: Mock = create_autospec(Verifier, spec_set=True, instance=True)
        verifier.verify.return_value = VerificationMother.passing()
        return verifier

    @pytest.fixture
    def corpus(self) -> Mock:
        corpus: Mock = create_autospec(Corpus, spec_set=True, instance=True)
        corpus.fingerprint_of_the_last_verification.return_value = _DIFF.fingerprint
        return corpus

    @pytest.fixture
    def action(self, reader: Mock, verifier: Mock, corpus: Mock) -> VerifySlice:
        skills: Mock = create_autospec(SkillLibrary, spec_set=True, instance=True)
        skills.directories.return_value = _YARDSTICK

        return VerifySlice(
            reader=reader, verifier=verifier, judge=JudgeMother.adversarial(), skills=skills, corpus=corpus
        )

    @staticmethod
    def _comparing() -> VerifySliceParams:
        return replace(_PARAMS, compares_with_the_last_verification=True)

    def test_a_diff_identical_to_the_one_last_judged_is_refused_before_the_judge_is_invoked(
        self, action: VerifySlice, verifier: Mock
    ) -> None:
        with pytest.raises(UnchangedDiffError):
            action.execute(self._comparing())

        verifier.verify.assert_not_called()

    def test_a_diff_that_was_not_judged_leaves_no_row_in_the_corpus(self, action: VerifySlice, corpus: Mock) -> None:
        with pytest.raises(UnchangedDiffError):
            action.execute(self._comparing())

        corpus.record.assert_not_called()

    def test_the_last_verification_is_asked_for_under_the_slice_that_was_asked_for(
        self, action: VerifySlice, corpus: Mock
    ) -> None:
        with pytest.raises(UnchangedDiffError):
            action.execute(self._comparing())

        corpus.fingerprint_of_the_last_verification.assert_called_once_with(
            SliceCoordinates(
                repo=_PARAMS.repo, issue=_PARAMS.issue, slice_id=CanonicalSliceId.of_text(_PARAMS.slice_id)
            )
        )

    def test_a_diff_that_differs_in_a_single_byte_is_judged_again(
        self, action: VerifySlice, reader: Mock, verifier: Mock
    ) -> None:
        reader.read.return_value = SliceDiffMother.of_the_slice(
            files=_DIFF.files, text=_DIFF.text.replace("return 2", "return 3")
        )

        action.execute(self._comparing())

        verifier.verify.assert_called_once()

    def test_a_slice_with_no_verification_before_has_nothing_to_compare_with_and_is_judged(
        self, action: VerifySlice, corpus: Mock, verifier: Mock
    ) -> None:
        corpus.fingerprint_of_the_last_verification.return_value = None

        action.execute(self._comparing())

        verifier.verify.assert_called_once()

    def test_an_invocation_that_did_not_judge_before_judges_even_an_identical_diff(
        self, action: VerifySlice, corpus: Mock, verifier: Mock
    ) -> None:
        action.execute(_PARAMS)

        verifier.verify.assert_called_once()
        corpus.fingerprint_of_the_last_verification.assert_not_called()
