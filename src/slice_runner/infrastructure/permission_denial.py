from __future__ import annotations

from slice_runner.infrastructure.open_vocabulary_model import OpenVocabularyModel


class PermissionDenial(OpenVocabularyModel):
    tool_name: str
    tool_input: dict[str, object]

    @property
    def denied_action(self) -> str:
        target = self.tool_input.get("file_path") or self.tool_input.get("path")

        return f"{self.tool_name} {target}" if isinstance(target, str) else self.tool_name
