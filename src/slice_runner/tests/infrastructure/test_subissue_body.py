from __future__ import annotations

from slice_runner.infrastructure.subissue_body import SubissueBody


class TestTheDesignsASubissueNames:
    def test_every_design_line_arrives_as_a_name_in_the_order_it_was_written(self) -> None:
        body = "INTENCION: x\nDISENO: tablero\nACEPTACION: y\nDISENO: detalle\n"

        parsed = SubissueBody.parse(body)

        assert parsed.designs == ("tablero", "detalle")

    def test_a_body_without_a_design_line_names_no_design(self) -> None:
        parsed = SubissueBody.parse("INTENCION: x\nACEPTACION: y\n")

        assert parsed.designs == ()
