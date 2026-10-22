from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel


class JsonSchema:
    _DEFINITIONS = "$defs"
    _REFERENCE = "$ref"
    _NOISE = frozenset({"title"})

    @classmethod
    def flat(cls, model: type[BaseModel]) -> dict[str, object]:
        schema = model.model_json_schema(by_alias=True)
        definitions: dict[str, dict[str, object]] = schema.pop(cls._DEFINITIONS, {})

        return cls._resolved_object(schema, definitions)

    @classmethod
    def _resolved_object(cls, node: dict[str, object], definitions: dict[str, dict[str, object]]) -> dict[str, object]:
        reference = node.get(cls._REFERENCE)
        if isinstance(reference, str):
            return cls._resolved_object(definitions[reference.rsplit("/", 1)[-1]], definitions)

        return {key: cls._resolved(value, definitions) for key, value in node.items() if key not in cls._NOISE}

    @classmethod
    def _resolved(cls, node: object, definitions: dict[str, dict[str, object]]) -> object:
        if isinstance(node, dict):
            return cls._resolved_object(node, definitions)
        if isinstance(node, list):
            return [cls._resolved(item, definitions) for item in node]

        return node
