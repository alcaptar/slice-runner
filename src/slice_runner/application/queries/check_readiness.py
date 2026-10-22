from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.check_verdict import CheckVerdict
from slice_runner.domain.exceptions import UnresolvableBaseError
from slice_runner.domain.readiness import Readiness
from slice_runner.domain.readiness_check import ReadinessCheck

if TYPE_CHECKING:
    from slice_runner.domain.branches import Branches
    from slice_runner.domain.forum import Forum
    from slice_runner.domain.plugin_registry import PluginRegistry
    from slice_runner.domain.program_version import ProgramVersion
    from slice_runner.domain.skill_library import SkillLibrary
    from slice_runner.domain.toolbox import Toolbox


@dataclass(frozen=True, kw_only=True, slots=True)
class CheckReadinessParams:
    repo: str | None = None
    worktree: str | None = None
    base: str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class CheckReadinessPorts:
    toolbox: Toolbox
    forum: Forum
    branches: Branches
    skills: SkillLibrary
    plugins: PluginRegistry
    program_version: ProgramVersion


class CheckReadiness:
    SKILLS: ClassVar[tuple[str, ...]] = ("slice-spec",)
    PLUGINS: ClassVar[tuple[str, ...]] = ("superpowers",)

    def __init__(self, *, ports: CheckReadinessPorts) -> None:
        self._toolbox = ports.toolbox
        self._forum = ports.forum
        self._branches = ports.branches
        self._skills = ports.skills
        self._plugins = ports.plugins
        self._program_version = ports.program_version

    def execute(self, params: CheckReadinessParams) -> Readiness:
        checks = [
            self._of_git(),
            self._of_gh(),
            self._of_claude(),
            *(self._of_skill(name) for name in self.SKILLS),
            *(self._of_plugin(name) for name in self.PLUGINS),
            self._of_version(),
        ]
        if params.repo is not None:
            checks.append(self._of_repo(params.repo))
        if params.worktree is not None and params.base is not None:
            checks.append(self._of_base(worktree=params.worktree, base=params.base))

        return Readiness(checks=tuple(checks))

    def _of_git(self) -> ReadinessCheck:
        version = self._toolbox.version_of("git")
        if version is None:
            return ReadinessCheck(
                name="git",
                verdict=CheckVerdict.MISSING,
                detail="not found on the PATH",
                fix="install git: https://git-scm.com/downloads",
            )

        return ReadinessCheck(name="git", verdict=CheckVerdict.READY, detail=version)

    def _of_gh(self) -> ReadinessCheck:
        version = self._toolbox.version_of("gh")
        if version is None:
            return ReadinessCheck(
                name="gh",
                verdict=CheckVerdict.MISSING,
                detail="not found on the PATH",
                fix="install the GitHub CLI: https://cli.github.com",
            )

        who = self._forum.authenticated_as()
        if who is None:
            return ReadinessCheck(
                name="gh", verdict=CheckVerdict.MISSING, detail="not authenticated", fix="gh auth login"
            )

        return ReadinessCheck(name="gh", verdict=CheckVerdict.READY, detail=f"authenticated as {who}")

    def _of_claude(self) -> ReadinessCheck:
        version = self._toolbox.version_of("claude")
        if version is None:
            return ReadinessCheck(
                name="claude",
                verdict=CheckVerdict.MISSING,
                detail="not found on the PATH",
                fix="install Claude Code: npm install -g @anthropic-ai/claude-code",
            )

        return ReadinessCheck(name="claude", verdict=CheckVerdict.READY, detail=version)

    def _of_skill(self, name: str) -> ReadinessCheck:
        path = self._skills.installed(name)
        if path is None:
            return ReadinessCheck(
                name=f"skill {name}",
                verdict=CheckVerdict.MISSING,
                detail="not installed",
                fix=self._install_fix(),
            )

        return ReadinessCheck(name=f"skill {name}", verdict=CheckVerdict.READY, detail=f"installed at {path}")

    def _of_plugin(self, name: str) -> ReadinessCheck:
        if self._plugins.enabled(name):
            return ReadinessCheck(name=f"plugin {name}", verdict=CheckVerdict.READY, detail="enabled")

        return ReadinessCheck(
            name=f"plugin {name}",
            verdict=CheckVerdict.MISSING,
            detail="not enabled",
            fix=f"/plugin marketplace add anthropics/claude-plugins-official && /plugin install {name}",
        )

    def _install_fix(self) -> str:
        return f"slice-runner update, to copy it under {self._skills.root()}"

    def _of_repo(self, repo: str) -> ReadinessCheck:
        if self._forum.can_read(repo=repo):
            return ReadinessCheck(name="repo", verdict=CheckVerdict.READY, detail=f"{repo} is readable")

        return ReadinessCheck(
            name="repo",
            verdict=CheckVerdict.MISSING,
            detail=f"{repo} is not readable",
            fix=f"gh auth login, or ask for access to {repo}",
        )

    def _of_base(self, *, worktree: str, base: str) -> ReadinessCheck:
        try:
            behind = self._branches.commits_behind_remote(worktree=worktree, base=base)
        except UnresolvableBaseError:
            return ReadinessCheck(
                name="base",
                verdict=CheckVerdict.MISSING,
                detail=f"{base} does not resolve against its remote",
            )

        if behind == 0:
            return ReadinessCheck(
                name="base", verdict=CheckVerdict.READY, detail=f"{base} is up to date with its remote"
            )

        return ReadinessCheck(
            name="base",
            verdict=CheckVerdict.WARNING,
            detail=f"{base} is {behind} commit(s) behind its remote",
            fix=f"git -C {worktree} branch -f {base} origin/{base}",
        )

    def _of_version(self) -> ReadinessCheck:
        return ReadinessCheck(name="version", verdict=CheckVerdict.READY, detail=self._program_version.read())
