from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.queries.check_readiness import CheckReadiness, CheckReadinessParams, CheckReadinessPorts
from slice_runner.domain.branches import Branches
from slice_runner.domain.check_verdict import CheckVerdict
from slice_runner.domain.exceptions import UnresolvableBaseError
from slice_runner.domain.forum import Forum
from slice_runner.domain.plugin_registry import PluginRegistry
from slice_runner.domain.program_version import ProgramVersion
from slice_runner.domain.skill_library import SkillLibrary
from slice_runner.domain.toolbox import Toolbox

if TYPE_CHECKING:
    from slice_runner.domain.readiness import Readiness
    from slice_runner.domain.readiness_check import ReadinessCheck

_SLICE_SPEC = Path("/home/someone/.claude/skills/slice-spec")
_VERSION = "0.1.0"


class TestCheckReadiness:
    @pytest.fixture
    def toolbox(self) -> Mock:
        toolbox: Mock = create_autospec(Toolbox, spec_set=True, instance=True)
        toolbox.version_of.return_value = "2.51.0"
        return toolbox

    @pytest.fixture
    def forum(self) -> Mock:
        forum: Mock = create_autospec(Forum, spec_set=True, instance=True)
        forum.authenticated_as.return_value = "someone"
        return forum

    @pytest.fixture
    def branches(self) -> Mock:
        branches: Mock = create_autospec(Branches, spec_set=True, instance=True)
        branches.commits_behind_remote.return_value = 0
        return branches

    @pytest.fixture
    def skills(self) -> Mock:
        skills: Mock = create_autospec(SkillLibrary, spec_set=True, instance=True)
        skills.root.return_value = Path("/home/someone/.claude")
        skills.installed.side_effect = lambda name: _SLICE_SPEC if name == "slice-spec" else None
        return skills

    @pytest.fixture
    def plugins(self) -> Mock:
        plugins: Mock = create_autospec(PluginRegistry, spec_set=True, instance=True)
        plugins.enabled.return_value = True
        return plugins

    @pytest.fixture
    def program_version(self) -> Mock:
        program_version: Mock = create_autospec(ProgramVersion, spec_set=True, instance=True)
        program_version.read.return_value = _VERSION
        return program_version

    @pytest.fixture
    def query(
        self,
        *,
        toolbox: Mock,
        forum: Mock,
        branches: Mock,
        skills: Mock,
        plugins: Mock,
        program_version: Mock,
    ) -> CheckReadiness:
        return CheckReadiness(
            ports=CheckReadinessPorts(
                toolbox=toolbox,
                forum=forum,
                branches=branches,
                skills=skills,
                plugins=plugins,
                program_version=program_version,
            )
        )

    @staticmethod
    def _check(readiness: Readiness, name: str) -> ReadinessCheck:
        return next(check for check in readiness.checks if check.name == name)

    def test_with_everything_in_place_the_readiness_is_ready(self, query: CheckReadiness) -> None:
        readiness = query.execute(CheckReadinessParams())

        assert readiness.ready
        assert all(check.verdict is CheckVerdict.READY for check in readiness.checks)

    def test_it_checks_exactly_the_one_skill_the_program_uses(self, query: CheckReadiness, skills: Mock) -> None:
        query.execute(CheckReadinessParams())

        checked = {call.args[0] for call in skills.installed.call_args_list}
        assert checked == {"slice-spec"}

    def test_a_machine_with_only_slice_spec_linked_reports_no_failed_skill_check(self, query: CheckReadiness) -> None:
        readiness = query.execute(CheckReadinessParams())

        skill_checks = [check for check in readiness.checks if check.name.startswith("skill ")]
        assert [check.name for check in skill_checks] == ["skill slice-spec"]
        assert all(check.verdict is CheckVerdict.READY for check in skill_checks)
        assert readiness.ready

    def test_a_missing_git_is_reported_as_missing_with_a_fix_command_and_breaks_readiness(
        self, query: CheckReadiness, toolbox: Mock
    ) -> None:
        toolbox.version_of.side_effect = lambda executable: None if executable == "git" else "2.1.4"

        readiness = query.execute(CheckReadinessParams())

        git = self._check(readiness, "git")
        assert git.verdict is CheckVerdict.MISSING
        assert git.fix
        assert not readiness.ready

    def test_gh_present_but_not_authenticated_is_missing_with_the_login_command_as_its_fix(
        self, query: CheckReadiness, forum: Mock
    ) -> None:
        forum.authenticated_as.return_value = None

        readiness = query.execute(CheckReadinessParams())

        gh = self._check(readiness, "gh")
        assert gh.verdict is CheckVerdict.MISSING
        assert gh.fix == "gh auth login"

    def test_gh_missing_outright_is_not_asked_whether_it_is_authenticated_too(
        self, query: CheckReadiness, toolbox: Mock, forum: Mock
    ) -> None:
        toolbox.version_of.side_effect = lambda executable: None if executable == "gh" else "2.1.4"

        readiness = query.execute(CheckReadinessParams())

        forum.authenticated_as.assert_not_called()
        assert self._check(readiness, "gh").verdict is CheckVerdict.MISSING

    def test_claude_is_asked_for_its_version_and_nothing_else_because_a_real_call_costs_money(
        self, query: CheckReadiness, toolbox: Mock
    ) -> None:
        query.execute(CheckReadinessParams())

        assert any(call.args == ("claude",) for call in toolbox.version_of.call_args_list)

    def test_a_missing_skill_is_reported_with_the_install_command_that_fixes_it(
        self, query: CheckReadiness, skills: Mock
    ) -> None:
        skills.installed.side_effect = lambda name: None

        readiness = query.execute(CheckReadinessParams())

        missing = self._check(readiness, "skill slice-spec")
        assert missing.verdict is CheckVerdict.MISSING
        assert missing.fix is not None
        assert "slice-runner update" in missing.fix
        assert "make install" not in missing.fix

    def test_a_missing_skill_fix_names_the_configuration_directory_the_doctor_just_looked_at(
        self, query: CheckReadiness, skills: Mock
    ) -> None:
        skills.root.return_value = Path("/repos/slice-runner-checkout/.claude-moved")
        skills.installed.side_effect = lambda name: None

        readiness = query.execute(CheckReadinessParams())

        missing = self._check(readiness, "skill slice-spec")
        assert missing.fix is not None
        assert "/repos/slice-runner-checkout/.claude-moved" in missing.fix
        assert "~/.claude" not in missing.fix

    def test_no_skill_fix_leaves_a_placeholder_to_fill_in_by_hand(self, query: CheckReadiness, skills: Mock) -> None:
        skills.installed.side_effect = None
        skills.installed.return_value = None

        readiness = query.execute(CheckReadinessParams())

        fixes = [check.fix for check in readiness.checks if check.name.startswith("skill ")]
        assert fixes
        assert all(fix is not None and "<checkout>" not in fix for fix in fixes)

    def test_the_superpowers_plugin_enabled_is_reported_as_ready(self, query: CheckReadiness, plugins: Mock) -> None:
        plugins.enabled.return_value = True

        readiness = query.execute(CheckReadinessParams())

        plugin = self._check(readiness, "plugin superpowers")
        assert plugin.verdict is CheckVerdict.READY
        assert readiness.ready

    def test_the_superpowers_plugin_not_enabled_is_reported_as_missing_and_breaks_readiness(
        self, query: CheckReadiness, plugins: Mock
    ) -> None:
        plugins.enabled.return_value = False

        readiness = query.execute(CheckReadinessParams())

        plugin = self._check(readiness, "plugin superpowers")
        assert plugin.verdict is CheckVerdict.MISSING
        assert plugin.fix
        assert not readiness.ready

    def test_without_repo_worktree_or_base_only_the_checks_that_need_none_of_them_run(
        self, query: CheckReadiness, forum: Mock, branches: Mock
    ) -> None:
        readiness = query.execute(CheckReadinessParams())

        assert {check.name for check in readiness.checks} == {
            "git",
            "gh",
            "claude",
            "skill slice-spec",
            "plugin superpowers",
            "version",
        }
        forum.can_read.assert_not_called()
        branches.commits_behind_remote.assert_not_called()

    def test_with_repo_readable_the_repo_check_is_ready(self, query: CheckReadiness, forum: Mock) -> None:
        forum.can_read.return_value = True

        readiness = query.execute(CheckReadinessParams(repo="alcaptar/slice-runner"))

        repo = self._check(readiness, "repo")
        assert repo.verdict is CheckVerdict.READY

    def test_with_repo_unreadable_the_repo_check_is_missing_with_a_fix_and_breaks_readiness(
        self, query: CheckReadiness, forum: Mock
    ) -> None:
        forum.can_read.return_value = False

        readiness = query.execute(CheckReadinessParams(repo="alcaptar/slice-runner"))

        repo = self._check(readiness, "repo")
        assert repo.verdict is CheckVerdict.MISSING
        assert repo.fix
        assert not readiness.ready

    def test_with_worktree_and_base_up_to_date_the_base_check_is_ready(
        self, query: CheckReadiness, branches: Mock
    ) -> None:
        branches.commits_behind_remote.return_value = 0

        readiness = query.execute(CheckReadinessParams(worktree="/repos/slice-runner", base="master"))

        base = self._check(readiness, "base")
        assert base.verdict is CheckVerdict.READY

    def test_with_worktree_and_base_behind_its_remote_the_base_check_warns_with_the_command_that_updates_it(
        self, query: CheckReadiness, branches: Mock
    ) -> None:
        branches.commits_behind_remote.return_value = 2

        readiness = query.execute(CheckReadinessParams(worktree="/repos/slice-runner", base="master"))

        base = self._check(readiness, "base")
        assert base.verdict is CheckVerdict.WARNING
        assert base.fix
        assert "master" in base.fix

    def test_a_lagging_base_warning_alone_does_not_flip_readiness_to_not_ready(
        self, query: CheckReadiness, branches: Mock
    ) -> None:
        branches.commits_behind_remote.return_value = 2

        readiness = query.execute(CheckReadinessParams(worktree="/repos/slice-runner", base="master"))

        assert readiness.ready

    def test_a_base_that_does_not_resolve_against_its_remote_is_reported_as_missing_naming_the_base(
        self, query: CheckReadiness, branches: Mock
    ) -> None:
        branches.commits_behind_remote.side_effect = UnresolvableBaseError("slice/05-never-pushed does not resolve")

        readiness = query.execute(CheckReadinessParams(worktree="/repos/slice-runner", base="slice/05-never-pushed"))

        base = self._check(readiness, "base")
        assert base.verdict is CheckVerdict.MISSING
        assert "slice/05-never-pushed" in base.detail
        assert not readiness.ready

    def test_worktree_without_base_does_not_run_the_base_check(self, query: CheckReadiness, branches: Mock) -> None:
        readiness = query.execute(CheckReadinessParams(worktree="/repos/slice-runner"))

        assert not any(check.name == "base" for check in readiness.checks)
        branches.commits_behind_remote.assert_not_called()

    def test_the_version_check_reports_exactly_the_version_of_the_installed_package(
        self, query: CheckReadiness
    ) -> None:
        readiness = query.execute(CheckReadinessParams())

        version = self._check(readiness, "version")
        assert version.verdict is CheckVerdict.READY
        assert version.detail == _VERSION

    def test_the_checks_that_came_from_the_checkout_are_gone(self, query: CheckReadiness) -> None:
        readiness = query.execute(CheckReadinessParams())

        names = {check.name for check in readiness.checks}
        assert names.isdisjoint({"provenance", "installed code", "checkout upstream"})

    def test_the_base_check_detail_names_how_many_commits_the_base_lags(
        self, query: CheckReadiness, branches: Mock
    ) -> None:
        branches.commits_behind_remote.return_value = 2

        readiness = query.execute(CheckReadinessParams(worktree="/repos/slice-runner", base="master"))

        base = self._check(readiness, "base")
        assert base.detail == "master is 2 commit(s) behind its remote"
        branches.commits_behind_remote.assert_called_once_with(worktree="/repos/slice-runner", base="master")
