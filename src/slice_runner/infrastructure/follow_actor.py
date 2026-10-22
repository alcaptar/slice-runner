from __future__ import annotations

from enum import StrEnum

from slice_runner.domain.activity_actor import ActivityActor


class FollowActor(StrEnum):
    IMPLEMENTER = "implementer"
    JUDGE = "judge"
    CONTROLS = "controls"

    @classmethod
    def of(cls, actor: ActivityActor) -> FollowActor:
        match actor:
            case ActivityActor.IMPLEMENTER:
                return cls.IMPLEMENTER
            case ActivityActor.JUDGE:
                return cls.JUDGE
            case ActivityActor.CONTROLS:
                return cls.CONTROLS

    def to_activity_actor(self) -> ActivityActor:
        match self:
            case FollowActor.IMPLEMENTER:
                return ActivityActor.IMPLEMENTER
            case FollowActor.JUDGE:
                return ActivityActor.JUDGE
            case FollowActor.CONTROLS:
                return ActivityActor.CONTROLS
