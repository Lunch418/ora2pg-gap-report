"""Declarative detector specs, and the factory that turns one into a
working detector function.

Most detectors in this project are the same three programs with different
constants. Written out by hand 100+ times, that meant every change to a
shared invariant was a hundred-file edit: the two false-positive fixes in
GAP-092/GAP-090 were each one regex, but a mistake in how *any* detector
attributes a finding to an object, or counts a line, had to be found and
fixed everywhere separately. This module makes the shared part exist
once.

What varies genuinely, and is therefore what a spec carries: which
dialect's lexer to use, which masked view to search, the pattern, the
severity, what to show as the snippet, and which message explains it.

What varies structurally is captured as three named strategies, because
the detectors really do scan in three different ways -- flattening them
into one parameterized template would be a lie that costs more than the
duplication did:

- `enclosing`: search the whole masked source and attribute each match to
  the routine containing it (enclosing_object_name_index). What almost
  every PL/SQL-body detector does.

- `table_columns`: find each CREATE TABLE, take its column-definition
  list, and search only inside that. For column-level properties, where a
  match outside the column list would be a different construct entirely
  and the owning object is the table, not a routine.

- `table_statement`: find each CREATE TABLE and search its whole
  statement, bounded by statement_end(). For table-level clauses that sit
  outside the column list.

Detectors whose logic is genuinely their own -- the seven that need
several passes, or a condition the pattern can't express -- stay
hand-written. A factory that grew a flag for each of those would end up
less readable than the code it replaced.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable

from .models import Finding

# Every spec's `strategy`. Named rather than free-form so a typo is a
# KeyError at import time, not a detector that silently finds nothing.
ENCLOSING = "enclosing"
TABLE_COLUMNS = "table_columns"
TABLE_STATEMENT = "table_statement"

# Which masked view to search. The three views differ in what they blank
# out -- see each lexer's own docstrings; the choice is per-detector and
# load-bearing, so it's part of the spec rather than a default.
MASK_STRINGS_AND_COMMENTS = "strings_and_comments"
MASK_DYNAMIC_SQL_VISIBLE = "dynamic_sql_visible"
MASK_COMMENTS_ONLY = "comments_only"

# A snippet is either a fixed label for the construct, or computed from
# the match when the useful thing to show is the matched text itself.
Snippet = str | Callable[[re.Match[str]], str]


@dataclasses.dataclass(frozen=True)
class DetectorSpec:
    """One detector, as data.

    `message_id` defaults to `name`: 105 of this project's detectors emit
    exactly one message, and giving it the detector's own name is what
    makes the id stable and guessable. bulk_collect, which emits three,
    is one of the hand-written detectors and sets its ids explicitly.
    """

    name: str
    dialect: str
    severity: str
    pattern: re.Pattern[str]
    strategy: str = ENCLOSING
    snippet: Snippet = ""
    message_id: str | None = None
    # Two views, because a detector can need to search one and report
    # positions from another. `search_mask` is what the pattern runs over;
    # `anchor_mask` is what line numbers and enclosing-object names are
    # computed from. They differ for the detectors that must see inside
    # EXECUTE IMMEDIATE string literals: those search the dynamic-SQL-
    # visible view, but a finding still has to name the routine and line
    # the reader will actually find in the file, which only the fully
    # masked view indexes correctly. Both views are position-preserving
    # (masking blanks characters, it never shortens), so an offset from
    # one is meaningful in the other -- that is the invariant the whole
    # two-view arrangement rests on.
    search_mask: str = MASK_STRINGS_AND_COMMENTS
    anchor_mask: str = MASK_STRINGS_AND_COMMENTS
    # Required by the two table strategies, meaningless to `enclosing`:
    # the pattern that finds the CREATE TABLE whose name becomes
    # object_name, capturing that name in group 1.
    table_pattern: re.Pattern[str] | None = None
    # Applied to the captured table name before it becomes object_name --
    # dialects quote identifiers differently (backticks, brackets), and
    # the lexer that knows how is the dialect's own.
    normalize_table_name: Callable[[str], str] | None = None

    def __post_init__(self) -> None:
        if self.strategy not in (ENCLOSING, TABLE_COLUMNS, TABLE_STATEMENT):
            raise ValueError(f"{self.name}: unknown strategy {self.strategy!r}")
        if self.strategy != ENCLOSING and self.table_pattern is None:
            raise ValueError(f"{self.name}: strategy {self.strategy!r} needs a table_pattern")

    @property
    def resolved_message_id(self) -> str:
        return self.message_id if self.message_id is not None else self.name


def _snippet_for(spec: DetectorSpec, match: re.Match[str]) -> str:
    return spec.snippet(match) if callable(spec.snippet) else spec.snippet


def _mask_fn(lex: object, mask: str) -> Callable[[str], str]:
    """The named masking function on `lex`. Named rather than passed as a
    callable so a spec stays plain data -- comparable, printable, and the
    same three strings whichever dialect's lexer ends up bound to it."""
    attr = {
        MASK_STRINGS_AND_COMMENTS: "mask_strings_and_comments",
        MASK_DYNAMIC_SQL_VISIBLE: "mask_dynamic_sql_visible",
        MASK_COMMENTS_ONLY: "mask_comments_only",
    }[mask]
    fn: Callable[[str], str] = getattr(lex, attr)
    return fn


def build(spec: DetectorSpec, lex: object) -> Callable[[str], list[Finding]]:
    """The detector function `spec` describes, bound to `lex` -- the
    dialect's lexer module, passed in rather than imported here so this
    module stays independent of which dialects exist."""
    search_fn = _mask_fn(lex, spec.search_mask)
    anchor_fn = _mask_fn(lex, spec.anchor_mask)
    line_at = lex.line_at  # type: ignore[attr-defined]

    def find_enclosing(source: str) -> list[Finding]:
        searched = search_fn(source)
        anchor = anchor_fn(source) if spec.anchor_mask != spec.search_mask else searched
        name_index = lex.enclosing_object_name_index(anchor)  # type: ignore[attr-defined]
        return [
            Finding(
                detector=spec.name,
                severity=spec.severity,
                object_name=lex.enclosing_object_name(name_index, m.start()),  # type: ignore[attr-defined]
                line=line_at(anchor, m.start()),
                snippet=_snippet_for(spec, m),
                message_id=spec.resolved_message_id,
            )
            for m in spec.pattern.finditer(searched)
        ]

    def find_in_table_columns(source: str) -> list[Finding]:
        clean = search_fn(source)
        findings: list[Finding] = []
        assert spec.table_pattern is not None  # guaranteed by __post_init__
        for table in spec.table_pattern.finditer(clean):
            span = lex.table_column_definition_list(clean, table.end())  # type: ignore[attr-defined]
            if span is None:
                # CREATE TABLE ... AS SELECT: no column-definition list to
                # search, and nothing about it is a finding.
                continue
            open_pos, close_pos = span
            columns = clean[open_pos + 1 : close_pos]
            for m in spec.pattern.finditer(columns):
                findings.append(
                    Finding(
                        detector=spec.name,
                        severity=spec.severity,
                        object_name=_table_name(spec, table),
                        line=line_at(clean, open_pos + 1 + m.start()),
                        snippet=_snippet_for(spec, m),
                        message_id=spec.resolved_message_id,
                    )
                )
        return findings

    def find_in_table_statement(source: str) -> list[Finding]:
        clean = search_fn(source)
        findings: list[Finding] = []
        assert spec.table_pattern is not None
        tables = list(spec.table_pattern.finditer(clean))
        for i, table in enumerate(tables):
            # Bounded by the next CREATE TABLE as well as by the statement
            # terminator: an unterminated statement would otherwise swallow
            # the rest of the file and attribute its matches to this table.
            next_start = tables[i + 1].start() if i + 1 < len(tables) else None
            end = lex.statement_end(clean, table.end(), next_start)  # type: ignore[attr-defined]
            statement = clean[table.end() : end]
            for m in spec.pattern.finditer(statement):
                findings.append(
                    Finding(
                        detector=spec.name,
                        severity=spec.severity,
                        object_name=_table_name(spec, table),
                        line=line_at(clean, table.end() + m.start()),
                        snippet=_snippet_for(spec, m),
                        message_id=spec.resolved_message_id,
                    )
                )
        return findings

    impl = {
        ENCLOSING: find_enclosing,
        TABLE_COLUMNS: find_in_table_columns,
        TABLE_STATEMENT: find_in_table_statement,
    }[spec.strategy]
    impl.__name__ = f"find_{spec.name}"
    impl.__qualname__ = impl.__name__
    # Point __module__ at the detector's own module, not at this factory.
    # core.detector_names() derives a detector's identity from exactly
    # this attribute, so leaving it as "…detector_spec" makes every built
    # detector claim to be one non-existent detector called
    # "detector_spec" -- which is what doctor.py caught the moment the
    # first batch was migrated. The name and the module basename are the
    # same string by this project's convention, enforced by doctor.py.
    impl.__module__ = f"{__package__}.detectors.{spec.name}"
    return impl


def _table_name(spec: DetectorSpec, table: re.Match[str]) -> str:
    name = table.group(1)
    if spec.normalize_table_name is not None:
        name = spec.normalize_table_name(name)
    return name.upper()
