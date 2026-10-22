from __future__ import annotations

from pydantic import Field

from slice_runner.infrastructure.open_vocabulary_model import OpenVocabularyModel


class ModelUsageEntry(OpenVocabularyModel):
    input_tokens: int = Field(alias="inputTokens", default=0)
    output_tokens: int = Field(alias="outputTokens", default=0)
    cache_read_input_tokens: int = Field(alias="cacheReadInputTokens", default=0)
    cache_creation_input_tokens: int = Field(alias="cacheCreationInputTokens", default=0)
