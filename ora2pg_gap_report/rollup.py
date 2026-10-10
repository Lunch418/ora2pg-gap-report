"""GROUP BY ... WITH ROLLUP / WITH CUBE -- T-SQL's and MySQL's old form of
GROUP BY ROLLUP (...) / CUBE (...), which PostgreSQL does not take
(GAP-151, GAP-152): the shape, and its rewrite for --fix."""

from __future__ import annotations

import re

WITH_ROLLUP_RE = re.compile(
    r"\bGROUP\s+BY\s+(?P<columns>(?:(?!\bGROUP\s+BY\b)[^;])*?)\s+WITH\s+(?P<kind>ROLLUP|CUBE)\b",
    re.IGNORECASE,
)


def rewrite_with_rollup(source: str, masked: str) -> tuple[str, int]:
    """`GROUP BY a, b WITH ROLLUP` -> `GROUP BY ROLLUP (a, b)` (and CUBE),
    found in `masked` -- strings and comments blanked, same length -- and
    applied to `source`."""
    matches = list(WITH_ROLLUP_RE.finditer(masked))
    for m in reversed(matches):
        columns = source[m.start("columns") : m.end("columns")].strip()
        head = source[m.start() : m.start("columns")]
        source = source[: m.start()] + f"{head}{m.group('kind').upper()} ({columns})" + source[m.end() :]
    return source, len(matches)
