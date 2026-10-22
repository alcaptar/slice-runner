from __future__ import annotations

import re
from typing import ClassVar


class GhTransientFailure:
    MARKERS: ClassVar[frozenset[str]] = frozenset(
        {
            "connection reset",
            "connection refused",
            "tls handshake",
            "i/o timeout",
            "context deadline exceeded",
            "unexpected eof",
            "unexpected end of json input",
            "temporary failure in name resolution",
            "dial tcp",
            "no such host",
            "network is unreachable",
            "secondary rate limit",
            "api rate limit exceeded",
            "internal server error",
            "bad gateway",
            "service unavailable",
            "gateway timeout",
            "no server is currently available to service your request",
            "error connecting to",
        }
    )

    HTTP_STATUS_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"http (\d)\d\d")

    @classmethod
    def of(cls, stderr: str) -> bool:
        lowered = stderr.lower()

        if any(marker in lowered for marker in cls.MARKERS):
            return True

        match = cls.HTTP_STATUS_PATTERN.search(lowered)

        return match is not None and match.group(1) == "5"
