from __future__ import annotations

from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, ConfigDict, ValidationError

if TYPE_CHECKING:
    from pydantic_core import ErrorDetails


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=False)

    @classmethod
    def _validated(cls, data: dict[str, object], where: str, rejection: type[ValueError]) -> Self:
        try:
            return cls.model_validate(data)
        except ValidationError as error:
            raise rejection(f"{where}: {cls._readable(error)}") from error

    @staticmethod
    def _present(**fields: object) -> dict[str, object]:
        return {name: value for name, value in fields.items() if value is not None}

    @classmethod
    def _readable(cls, error: ValidationError) -> str:
        return "; ".join(cls._detail(reported) for reported in error.errors())

    @staticmethod
    def _detail(reported: ErrorDetails) -> str:
        where = ".".join(str(step) for step in reported["loc"])
        complaint = f"`{where}` {reported['msg'].lower()}"
        given = reported["input"]
        if isinstance(given, str | int | float | type(None)):
            return f"{complaint} (got {given!r})"

        return complaint

    def to_contract(self) -> dict[str, object]:
        return self.model_dump(by_alias=True, exclude_none=True, mode="json")
