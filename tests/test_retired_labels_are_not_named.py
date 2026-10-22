from __future__ import annotations

from typing import ClassVar

from conftest import _ROOT, _read, _tracked

from slice_runner.domain.retired_issue_label import RetiredIssueLabel


class RetiredLabelsInMarkdown:
    EXEMPT: ClassVar[frozenset[str]] = frozenset(
        {
            "docs/12-factor.md",
            "docs/maturity-map.md",
            "docs/research-agent-loops.md",
        }
    )

    @classmethod
    def naming(cls, documents: dict[str, str]) -> dict[str, list[str]]:
        found: dict[str, list[str]] = {}
        for path, text in documents.items():
            if path in cls.EXEMPT:
                continue
            names = [label.value for label in RetiredIssueLabel if label.value in text]
            if names:
                found[path] = names

        return found


class TestNoMarkdownNamesARetiredLabel:
    def test_the_tracked_markdown_of_the_repo_names_none_of_them(self) -> None:
        documents = {path: _read(_ROOT / path) for path in _tracked("*.md")}

        assert RetiredLabelsInMarkdown.naming(documents) == {}

    def test_a_document_that_names_one_is_caught_unless_it_is_one_of_the_exempt(self) -> None:
        documents = {
            "README.md": "la subissue queda `bloqueada:sin-cambios`",
            "docs/12-factor.md": "`bloqueada:verify`",
        }

        assert RetiredLabelsInMarkdown.naming(documents) == {"README.md": ["bloqueada:sin-cambios"]}

    def test_every_retired_label_is_scanned_for(self) -> None:
        documents = {"a.md": " ".join(label.value for label in RetiredIssueLabel)}

        assert RetiredLabelsInMarkdown.naming(documents) == {"a.md": [label.value for label in RetiredIssueLabel]}
