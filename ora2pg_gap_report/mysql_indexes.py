"""The index clauses inside a MySQL CREATE TABLE column list, as mysqldump
writes them -- `KEY idx (a)`, `INDEX idx (a, b)`, `UNIQUE KEY uq (a)`,
`KEY idx (note(20))` -- for the detectors and the --prepare rewrite that
deal with them (GAP-073, GAP-127, GAP-128)."""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Iterator

from .mysql_lex import TABLE_HEAD, mask_strings_and_comments, qualified_name_pattern, table_column_definition_list

_TABLE_RE = re.compile(qualified_name_pattern(TABLE_HEAD), re.IGNORECASE)
_NAME = r"(?:`[^`]+`|[A-Za-z_][A-Za-z0-9_$]*)"
_ITEM_RE = re.compile(
    rf"\s*(?:(UNIQUE|FULLTEXT|SPATIAL)\s+)?(KEY|INDEX)\b\s*(?!\()({_NAME})?\s*(\(.*\))(.*)\Z",
    re.IGNORECASE | re.DOTALL,
)
_COLUMN_RE = re.compile(rf"\s*({_NAME})\s*(?:\(\s*(\d+)\s*\))?\s*(?:ASC|DESC)?\s*\Z", re.IGNORECASE)


def bare(name: str) -> str:
    return name[1:-1] if name.startswith("`") else name


@dataclasses.dataclass(frozen=True)
class IndexClause:
    table: str  # bare
    qualifier: str | None  # UNIQUE / FULLTEXT / SPATIAL, upper case
    keyword: str  # KEY or INDEX, as written
    keyword_start: int
    name: str | None  # as written, with its backquotes
    name_start: int  # where the name is, or would go
    columns: tuple[tuple[str, int | None], ...]  # (bare name, prefix length)
    start: int  # of the clause, in the source

    @property
    def has_prefix(self) -> bool:
        return any(length is not None for _, length in self.columns)


def _top_level_items(text: str, offset: int) -> Iterator[tuple[int, str]]:
    depth = 0
    start = 0
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            yield offset + start, text[start:i]
            start = i + 1
    yield offset + start, text[start:]


def index_clauses(source: str) -> list[IndexClause]:
    """Every KEY/INDEX clause of every CREATE TABLE in `source`, in order.
    PRIMARY KEY and FOREIGN KEY are not index clauses here."""
    clean = mask_strings_and_comments(source)
    clauses: list[IndexClause] = []
    for table in _TABLE_RE.finditer(clean):
        span = table_column_definition_list(clean, table.end())
        if span is None:
            continue
        body_start = span[0] + 1
        for item_start, item in _top_level_items(clean[body_start : span[1]], body_start):
            m = _ITEM_RE.match(item)
            if m is None:
                continue
            inner = m.group(4)[1 : m.group(4).rfind(")")]
            columns: list[tuple[str, int | None]] = []
            for _, column in _top_level_items(inner, 0):
                c = _COLUMN_RE.match(column)
                if c is None:
                    columns = []
                    break
                columns.append((bare(c.group(1)), int(c.group(2)) if c.group(2) else None))
            if not columns:
                continue
            name_start = item_start + (m.start(3) if m.group(3) else m.end(2))
            clauses.append(
                IndexClause(
                    table=bare(table.group(1)),
                    qualifier=m.group(1).upper() if m.group(1) else None,
                    keyword=m.group(2),
                    keyword_start=item_start + m.start(2),
                    name=m.group(3),
                    name_start=name_start,
                    columns=tuple(columns),
                    start=item_start + len(item) - len(item.lstrip()),
                )
            )
    return clauses


def colliding_names(clauses: list[IndexClause]) -> set[str]:
    """Names (lower case) given to plain indexes on more than one table:
    MySQL scopes an index name to its table, PostgreSQL to the schema."""
    tables: dict[str, set[str]] = {}
    for c in clauses:
        if c.qualifier is None and c.name is not None:
            tables.setdefault(bare(c.name).lower(), set()).add(c.table.lower())
    return {name for name, owners in tables.items() if len(owners) > 1}
