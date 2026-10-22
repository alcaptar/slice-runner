from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

from slice_runner.infrastructure.turn_log import TurnLog
from slice_runner.infrastructure.turn_payload import TurnPayload

if TYPE_CHECKING:
    from slice_runner.infrastructure.turn_log import HarnessTurn


class StderrTurnLog(TurnLog):
    def observe(self, turn: HarnessTurn) -> None:
        print(json.dumps(TurnPayload.from_domain(turn).to_contract(), ensure_ascii=False), file=sys.stderr)
