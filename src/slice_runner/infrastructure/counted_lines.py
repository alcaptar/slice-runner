from __future__ import annotations


class CountedLines:
    @staticmethod
    def of(heading: str, entries: tuple[str, ...]) -> list[str]:
        return [f"- {heading} ({len(entries)}):", *(f"  - {entry}" for entry in entries)]
