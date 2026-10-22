from __future__ import annotations

from pydantic import model_validator

from slice_runner.infrastructure.contract_model import ContractModel


class OpenVocabularyModel(ContractModel):
    @model_validator(mode="before")
    @classmethod
    def projected(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        consumed = {field.alias or name for name, field in cls.model_fields.items()}

        return {key: value for key, value in data.items() if key in consumed}
