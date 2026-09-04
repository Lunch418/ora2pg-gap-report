import re

from ..models import Finding
from ..mysql_lex import (
    line_at,
    mask_strings_and_comments,
    qualified_name_pattern,
    table_column_definition_list,
)

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
# A KEY clause in the column list, with whatever qualifier precedes it.
# The qualifier is captured rather than excluded by a lookbehind so that
# PRIMARY/UNIQUE/FOREIGN/FULLTEXT/SPATIAL KEY -- each of which ora2pg
# either converts correctly (PRIMARY, UNIQUE) or has its own gap
# (FULLTEXT: GAP-072, SPATIAL: GAP-074) -- can be skipped by inspecting
# group(1), which Python's fixed-width-only lookbehind can't express in
# one pattern.
_KEY_RE = re.compile(
    r"\b(?:(PRIMARY|UNIQUE|FOREIGN|FULLTEXT|SPATIAL)\s+)?KEY\b",
    re.IGNORECASE,
)


def find_mysql_key_indexes(source: str) -> list[Finding]:
    """Detect a bare `KEY <name> (<cols>)` index clause inside a MySQL
    CREATE TABLE column list -- mysqldump's own default spelling. ora2pg
    -m leaves the bare keyword plus the index name where a column
    definition was expected, and the CREATE TABLE fails to load. The
    `INDEX` spelling and `UNIQUE KEY` both convert correctly and are
    deliberately not flagged. See docs/research/gap-073-mysql-key-index.md."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _TABLE_RE.finditer(clean):
        span = table_column_definition_list(clean, m.end())
        if span is None:
            continue  # bare CTAS with no column-definition list at all
        open_pos, close_pos = span
        column_list = clean[open_pos + 1 : close_pos]

        for key_match in _KEY_RE.finditer(column_list):
            if key_match.group(1) is not None:
                continue  # PRIMARY/UNIQUE/FOREIGN/FULLTEXT/SPATIAL -- not this gap
            findings.append(
                Finding(
                    detector="mysql_key_index",
                    severity="high",
                    object_name=m.group(1).upper(),
                    line=line_at(clean, open_pos + 1 + key_match.start()),
                    snippet="KEY",
                    message_id="mysql_key_index",
                )
            )

    return findings
