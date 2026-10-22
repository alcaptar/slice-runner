from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.judge import Judge
    from slice_runner.domain.slice_under_review import SliceUnderReview
    from slice_runner.domain.verification import Verification


class Verifier(ABC):
    @abstractmethod
    def verify(self, judge: Judge, review: SliceUnderReview) -> Verification: ...
