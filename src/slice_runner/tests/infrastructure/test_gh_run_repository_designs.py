from __future__ import annotations

import json

from slice_runner.infrastructure.gh_run_repository import GhRunRepository
from slice_runner.infrastructure.process import ProcessOutput
from slice_runner.tests.doubles import GhCallDoubles, ScriptedProcess
from slice_runner.tests.mothers.design_mother import DesignMother
from slice_runner.tests.mothers.gh_response_mother import GhResponseMother

_REPO = "alcaptar/slice-runner"


class TestReadingTheDesignsOfAFeature:
    @staticmethod
    def _repository(payload: object) -> GhRunRepository:
        process = ScriptedProcess(ProcessOutput(code=0, stdout=json.dumps(payload), stderr=""))

        return GhRunRepository(call=GhCallDoubles.wired(process))

    def test_the_designs_the_parent_declares_arrive_with_their_html(self) -> None:
        body = f"## Diseno\n### tablero\n```html\n{DesignMother.BOARD_HTML}\n```\n"
        payload = {
            "body": body,
            "subIssuesSummary": {"completed": 0, "percentCompleted": 0, "total": 1},
            "state": "OPEN",
        }

        parent = self._repository(payload).read_parent(repo=_REPO, issue=43, slice_repo=None)

        assert parent.designs == (DesignMother.board(),)

    def test_every_design_line_of_a_subissue_arrives_as_the_name_of_a_design_in_order(self) -> None:
        entry = {**GhResponseMother.children_of_parent()[0], "body": "INTENCION: x\nDISENO: tablero\nDISENO: detalle\n"}

        children = self._repository([entry]).read_children(repo=_REPO, parent=43, expected=1)

        assert children[0].design_names == ("tablero", "detalle")
