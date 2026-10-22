from __future__ import annotations

from slice_runner.domain.exceptions import ImpossibleTransitionError
from slice_runner.domain.worktree_retirement import WorktreeRetirement
from slice_runner.infrastructure.automation_mark import AutomationMark


class KeptWorktreeComment:
    @classmethod
    def rendered(cls, *, path: str, retirement: WorktreeRetirement) -> str:
        return "\n\n".join(
            [
                f"El worktree de esta slice se ha quedado en `{path}`: {cls._reason_of(retirement)}.",
                *cls._resolution_of(path, retirement),
                AutomationMark.TEXT,
            ]
        )

    @staticmethod
    def removal_command(path: str) -> str:
        return f"git worktree remove {path}"

    @staticmethod
    def _reason_of(retirement: WorktreeRetirement) -> str:
        match retirement:
            case WorktreeRetirement.KEPT_UNCOMMITTED_WORK:
                return "tiene cambios sin comitear, y retirarlo los perderia"
            case WorktreeRetirement.KEPT_LOCAL_ONLY_COMMITS:
                return "su rama tiene commits que solo existen en local, y retirarlo los perderia"
            case WorktreeRetirement.KEPT_UNVERIFIABLE:
                return "no se pudo comprobar si retirarlo perdia algo, asi que se conserva"
            case WorktreeRetirement.KEPT_REMOVAL_FAILED:
                return "git no pudo retirarlo, con lo que sigue ahi"
            case WorktreeRetirement.KEPT_FOR_RESUMING:
                return "el run no termino entregado y se conserva para reanudar"
            case WorktreeRetirement.KEPT_UNEXPECTED:
                return "no se esperaba ningun worktree de esta slice, asi que no se reutiliza ni se monta encima"
            case WorktreeRetirement.RETIRED | WorktreeRetirement.NOT_MOUNTED:
                raise ImpossibleTransitionError(f"a worktree that is `{retirement}` has no comment to publish")

    @classmethod
    def _resolution_of(cls, path: str, retirement: WorktreeRetirement) -> list[str]:
        if retirement is not WorktreeRetirement.KEPT_UNEXPECTED:
            return []

        return [
            "Resuelvelo a mano y vuelve a lanzar la slice. "
            f"Para quitarlo, si no hay nada que salvar: `{cls.removal_command(path)}`"
        ]
