from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.ci import Ci
from slice_runner.domain.ci_status import CiStatus
from slice_runner.domain.exceptions import CiCommandFailedError, UnreadableCiError
from slice_runner.infrastructure.gh_check_payload import GhCheckPayload

if TYPE_CHECKING:
    from slice_runner.infrastructure.gh_call import GhCall


class GhCi(Ci):
    PASSED_BUCKET: ClassVar[str] = "pass"
    PENDING_BUCKET: ClassVar[str] = "pending"
    RED_BUCKETS: ClassVar[frozenset[str]] = frozenset({"fail", "cancel"})
    OK_BUCKETS: ClassVar[frozenset[str]] = frozenset({PASSED_BUCKET, "skipping"})
    KNOWN_BUCKETS: ClassVar[frozenset[str]] = RED_BUCKETS | OK_BUCKETS | frozenset({PENDING_BUCKET})

    def __init__(self, *, call: GhCall) -> None:
        self._call = call

    def status(self, *, repo: str, pull_request: int) -> CiStatus:
        argv = ["gh", "pr", "checks", str(pull_request), "--repo", repo, "--json", "name,bucket"]
        outcome = self._call.run(argv, stdin="", safe_to_repeat=True)
        if outcome.output.code != 0 and outcome.output.stderr:
            raise CiCommandFailedError(f"gh pr checks failed for {repo}#{pull_request}: {outcome.reason}")

        return self._classified(self._checks(outcome.output.stdout))

    @classmethod
    def _checks(cls, stdout: str) -> list[GhCheckPayload]:
        data = cls._decoded(stdout)
        if not isinstance(data, list):
            raise UnreadableCiError(f"gh has to return an array of checks, not {type(data).__name__}")

        return [GhCheckPayload.from_dict(cls._object(item)) for item in data]

    @staticmethod
    def _decoded(stdout: str) -> object:
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as error:
            raise UnreadableCiError(f"gh did not return JSON: {error}") from error

    @staticmethod
    def _object(item: object) -> dict[str, object]:
        if not isinstance(item, dict):
            raise UnreadableCiError(f"every check has to be an object, not {type(item).__name__}")

        return item

    @classmethod
    def _classified(cls, checks: list[GhCheckPayload]) -> CiStatus:
        if not checks:
            return CiStatus.NO_CHECKS

        buckets = {check.bucket for check in checks}
        if buckets - cls.KNOWN_BUCKETS:
            return CiStatus.UNKNOWN
        if buckets & cls.RED_BUCKETS:
            return CiStatus.RED
        if cls.PENDING_BUCKET in buckets:
            return CiStatus.PENDING
        if cls.PASSED_BUCKET not in buckets:
            return CiStatus.NO_CHECKS

        return CiStatus.GREEN
