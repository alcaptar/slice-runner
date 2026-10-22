from __future__ import annotations

from enum import StrEnum


class PullRequestReviewState(StrEnum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes-requested"
    COMMENTED = "commented"
    DISMISSED = "dismissed"
    PENDING = "pending"
