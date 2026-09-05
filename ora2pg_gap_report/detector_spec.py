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

- `match_named`: search the whole masked source, and take the object's
  name from the match itself. For standalone schema-level DDL -- CREATE
  BITMAP INDEX, CREATE TYPE, CREATE CONTEXT -- where there is no
  enclosing routine to attribute to and the failing object is the one
  being created.

- `statement_clause`: find each statement that `statement_pattern`
  introduces (which also names the object), search its text for the
  clause, and report at most one finding per statement, at the clause.
  For properties a statement either has or doesn't -- ORGANIZATION
  INDEX, INVISIBLE, READ ONLY: a second match inside the same statement
  restates the same fact rather than being a second problem.

Roughly a third of the detectors stay hand-written, and should. They are
the ones whose logic is genuinely their own: several passes over the
source (package_state walks a package's declarations, then its body),
a name built from more than the match (nested_subprogram reports
OUTER.INNER), more than one message from one scan (bulk_collect emits
three), or a condition no pattern expresses (mssql_parameterless_
procedure has to look at the routine's header text between the name and
the AS to see whether any parameter is declared). A factory that grew a
flag for each of those would end up less readable than the code it
replaced -- so the rule for a new detector is: if it fits a strategy as
it stands, write a spec; if making it fit would mean adding a flag,
write the function.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable

from .models import Finding

# Every spec's `strategy`. Named rather than free-form so a typo is a
# KeyError at import time, not a detector that silently finds nothing.
ENCLOSING = "enclosing"
MATCH_NAMED = "match_named"
TABLE_COLUMNS = "table_columns"
TABLE_STATEMENT = "table_statement"
STATEMENT_CLAUSE = "statement_clause"

# The strategies that scan a statement found by `statement_pattern`
# rather than the whole source, and therefore require one.
_STATEMENT_SCOPED = (TABLE_COLUMNS, TABLE_STATEMENT, STATEMENT_CLAUSE)

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
    statement_pattern: re.Pattern[str] | None = None
    # Applied to the captured name before it becomes object_name --
    # dialects quote identifiers differently (backticks, brackets), and
    # the lexer that knows how is the dialect's own. Uppercasing happens
    # after, unconditionally, so object_name is comparable across
    # detectors regardless of how the source spelled it.
    normalize_object_name: Callable[[str], str] | None = None
    # Which group of the naming match holds the object's name. Group 1
    # for all but one detector, which needs the pattern's own shape to
    # put it elsewhere.
    name_group: int = 1

    def __post_init__(self) -> None:
        if self.strategy not in (
            ENCLOSING, MATCH_NAMED, TABLE_COLUMNS, TABLE_STATEMENT, STATEMENT_CLAUSE
        ):
            raise ValueError(f"{self.name}: unknown strategy {self.strategy!r}")
        if self.strategy in _STATEMENT_SCOPED and self.statement_pattern is None:
            raise ValueError(f"{self.name}: strategy {self.strategy!r} needs a statement_pattern")
        if self.strategy not in _STATEMENT_SCOPED and self.statement_pattern is not None:
            raise ValueError(
                f"{self.name}: strategy {self.strategy!r} scans the whole source, so a "
                "statement_pattern would be silently ignored"
            )

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

    def find_match_named(source: str) -> list[Finding]:
        searched = search_fn(source)
        anchor = anchor_fn(source) if spec.anchor_mask != spec.search_mask else searched
        return [
            Finding(
                detector=spec.name,
                severity=spec.severity,
                object_name=_object_name(spec, m),
                line=line_at(anchor, m.start()),
                snippet=_snippet_for(spec, m),
                message_id=spec.resolved_message_id,
            )
            for m in spec.pattern.finditer(searched)
        ]

    def find_statement_clause(source: str) -> list[Finding]:
        clean = search_fn(source)
        findings: list[Finding] = []
        assert spec.statement_pattern is not None  # guaranteed by __post_init__
        heads = list(spec.statement_pattern.finditer(clean))
        for i, head in enumerate(heads):
            # Bounded by the next statement head as well as by the
            # terminator: DBMS_METADATA.GET_DDL emits no ';' by default,
            # and without this bound an unterminated statement would
            # swallow the rest of the file and claim a later statement's
            # clause as its own.
            next_start = heads[i + 1].start() if i + 1 < len(heads) else None
            end = lex.statement_end(clean, head.end(), next_start)  # type: ignore[attr-defined]
            clause = spec.pattern.search(clean[head.end() : end])
            if clause is None:
                continue
            findings.append(
                Finding(
                    detector=spec.name,
                    severity=spec.severity,
                    object_name=_object_name(spec, head),
                    line=line_at(clean, head.end() + clause.start()),
                    snippet=_snippet_for(spec, clause),
                    message_id=spec.resolved_message_id,
                )
            )
        return findings

    def find_in_table_columns(source: str) -> list[Finding]:
        clean = search_fn(source)
        findings: list[Finding] = []
        assert spec.statement_pattern is not None  # guaranteed by __post_init__
        for table in spec.statement_pattern.finditer(clean):
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
                        object_name=_object_name(spec, table),
                        line=line_at(clean, open_pos + 1 + m.start()),
                        snippet=_snippet_for(spec, m),
                        message_id=spec.resolved_message_id,
                    )
                )
        return findings

    def find_in_table_statement(source: str) -> list[Finding]:
        clean = search_fn(source)
        findings: list[Finding] = []
        assert spec.statement_pattern is not None
        tables = list(spec.statement_pattern.finditer(clean))
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
                        object_name=_object_name(spec, table),
                        line=line_at(clean, table.end() + m.start()),
                        snippet=_snippet_for(spec, m),
                        message_id=spec.resolved_message_id,
                    )
                )
        return findings

    impl = {
        ENCLOSING: find_enclosing,
        MATCH_NAMED: find_match_named,
        TABLE_COLUMNS: find_in_table_columns,
        TABLE_STATEMENT: find_in_table_statement,
        STATEMENT_CLAUSE: find_statement_clause,
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


def _object_name(spec: DetectorSpec, match: re.Match[str]) -> str:
    """The object a finding is attributed to, taken from the match that
    names it."""
    name = match.group(spec.name_group)
    if spec.normalize_object_name is not None:
        name = spec.normalize_object_name(name)
    return name.upper()
