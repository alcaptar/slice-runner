from __future__ import annotations


class PriorArtBlock:
    @staticmethod
    def of(prior_art: str) -> list[str]:
        stripped = prior_art.strip()
        if not stripped:
            return []

        return ["- lo que ya existe en el repo:", *(f"  {line}" for line in stripped.splitlines())]
