from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.conversation import Conversation


class ConversationLog(ABC):
    @abstractmethod
    def read(self, *, session: str, worktree: str) -> Conversation: ...
