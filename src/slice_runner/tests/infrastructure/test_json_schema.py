from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from slice_runner.infrastructure.json_schema import JsonSchema


class _Innermost(BaseModel):
    value: str


class _Middle(BaseModel):
    innermost: _Innermost
    alternatives: list[_Innermost] = Field(default_factory=list)


class _Outermost(BaseModel):
    model_config = ConfigDict(extra="forbid")

    middle: _Middle
    optional: int | None = None


class TestFlatteningAModelSchema:
    def test_a_reference_two_levels_deep_is_resolved_and_not_only_the_first_one(self) -> None:
        assert self._at("properties", "middle", "properties", "innermost") == {
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "type": "object",
        }

    def test_a_reference_inside_a_list_of_items_is_resolved_too(self) -> None:
        alternatives = self._at("properties", "middle", "properties", "alternatives")

        assert self._object(alternatives["items"])["type"] == "object"

    def test_the_definitions_block_does_not_survive_the_flattening(self) -> None:
        assert "$defs" not in JsonSchema.flat(_Outermost)

    def test_the_titles_go_because_they_only_spend_tokens_of_the_prompt(self) -> None:
        assert "title" not in str(JsonSchema.flat(_Outermost))

    def test_what_the_model_declares_survives_untouched(self) -> None:
        schema = JsonSchema.flat(_Outermost)

        assert schema["additionalProperties"] is False
        assert schema["required"] == ["middle"]
        assert self._at("properties", "optional")["anyOf"] == [{"type": "integer"}, {"type": "null"}]

    @classmethod
    def _at(cls, *path: str) -> dict[str, object]:
        node: object = JsonSchema.flat(_Outermost)
        for key in path:
            node = cls._object(node)[key]

        return cls._object(node)

    @staticmethod
    def _object(node: object) -> dict[str, object]:
        assert isinstance(node, dict)

        return node
