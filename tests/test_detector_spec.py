"""Tests for the detector factory itself.

Each detector has its own test file proving what it finds; these prove
the machinery those 70-odd detectors are now built out of -- that each
strategy scans the way it says it does, that a malformed spec fails at
import time rather than becoming a detector that silently finds nothing,
and that a built function is indistinguishable from a hand-written one
where the rest of the project inspects it.
"""

import re

import pytest

from ora2pg_gap_report import mssql_lex, plsql_lex
from ora2pg_gap_report.detector_spec import (
    ENCLOSING,
    MASK_DYNAMIC_SQL_VISIBLE,
    MATCH_NAMED,
    STATEMENT_CLAUSE,
    TABLE_COLUMNS,
    TABLE_STATEMENT,
    DetectorSpec,
    build,
)


def _spec(**overrides):
    base = dict(
        name="example",
        dialect="oracle",
        severity="high",
        pattern=re.compile(r"\bWIDGET\b", re.IGNORECASE),
        snippet="WIDGET",
    )
    base.update(overrides)
    return DetectorSpec(**base)


# --- what a malformed spec does ----------------------------------------
# All at construction time: a spec is built at import, so a mistake here
# is an ImportError on a broken build rather than a detector that quietly
# reports nothing on every scan for as long as nobody looks.


def test_an_unknown_strategy_is_rejected():
    with pytest.raises(ValueError, match="unknown strategy"):
        _spec(strategy="whatever")


def test_a_statement_scoped_strategy_without_a_statement_pattern_is_rejected():
    for strategy in (TABLE_COLUMNS, TABLE_STATEMENT, STATEMENT_CLAUSE):
        with pytest.raises(ValueError, match="needs a statement_pattern"):
            _spec(strategy=strategy)


def test_a_whole_source_strategy_with_a_statement_pattern_is_rejected():
    # Not merely useless: it reads as if the detector were scoped to those
    # statements when it is actually scanning the whole file, which is a
    # difference in what gets reported, not just in style.
    for strategy in (ENCLOSING, MATCH_NAMED):
        with pytest.raises(ValueError, match="silently ignored"):
            _spec(strategy=strategy, statement_pattern=re.compile("x"))


# --- message ids --------------------------------------------------------


def test_message_id_defaults_to_the_detector_name():
    assert _spec().resolved_message_id == "example"


def test_an_explicit_message_id_wins():
    assert _spec(message_id="something_else").resolved_message_id == "something_else"


# --- identity of a built detector --------------------------------------


def test_a_built_detector_claims_its_own_module_not_the_factory():
    # core.detector_names() derives a detector's identity from exactly
    # this attribute. Inheriting the factory's module made every built
    # detector claim to be one non-existent detector called
    # "detector_spec".
    found = build(_spec(), plsql_lex)
    assert found.__module__ == "ora2pg_gap_report.detectors.example"
    assert found.__name__ == "find_example"


# --- each strategy scans the way it claims ------------------------------


def test_enclosing_attributes_a_match_to_the_routine_containing_it():
    found = build(_spec(), plsql_lex)(
        "CREATE PROCEDURE p1 AS BEGIN NULL; END;\n"
        "CREATE PROCEDURE p2 AS BEGIN widget; END;\n"
    )
    assert [(f.object_name, f.line) for f in found] == [("P2", 2)]


def test_match_named_takes_the_object_name_from_the_match_itself():
    found = build(
        _spec(
            strategy=MATCH_NAMED,
            pattern=re.compile(r"\bCREATE\s+WIDGET\s+(\w+)", re.IGNORECASE),
        ),
        plsql_lex,
    )("CREATE WIDGET sprocket;\n")
    assert [f.object_name for f in found] == ["SPROCKET"]


def test_match_named_can_take_the_name_from_another_group():
    found = build(
        _spec(
            strategy=MATCH_NAMED,
            pattern=re.compile(r"\bCREATE\s+(\w+)\s+(\w+)", re.IGNORECASE),
            name_group=2,
        ),
        plsql_lex,
    )("CREATE WIDGET sprocket;\n")
    assert [f.object_name for f in found] == ["SPROCKET"]


def test_normalize_object_name_runs_before_uppercasing():
    found = build(
        _spec(
            strategy=MATCH_NAMED,
            pattern=re.compile(r"\bCREATE\s+WIDGET\s+(\S+)", re.IGNORECASE),
            normalize_object_name=lambda n: n.strip("[]"),
        ),
        mssql_lex,
    )("CREATE WIDGET [sprocket]\n")
    assert [f.object_name for f in found] == ["SPROCKET"]


def test_table_columns_searches_only_the_column_definition_list():
    spec = _spec(
        strategy=TABLE_COLUMNS,
        statement_pattern=re.compile(r"\bCREATE\s+TABLE\s+(\w+)", re.IGNORECASE),
    )
    found = build(spec, plsql_lex)(
        "CREATE TABLE t (a NUMBER, b WIDGET) TABLESPACE widget_ts;\n"
    )
    # The TABLESPACE clause sits outside the column list and is a
    # different construct that happens to share the word.
    assert [(f.object_name, f.snippet) for f in found] == [("T", "WIDGET")]


def test_table_columns_skips_a_create_table_as_select():
    spec = _spec(
        strategy=TABLE_COLUMNS,
        statement_pattern=re.compile(r"\bCREATE\s+TABLE\s+(\w+)", re.IGNORECASE),
    )
    assert build(spec, plsql_lex)("CREATE TABLE t AS SELECT widget FROM u;\n") == []


def test_table_statement_reports_every_match_in_the_statement():
    spec = _spec(
        strategy=TABLE_STATEMENT,
        statement_pattern=re.compile(r"\bCREATE\s+TABLE\s+(\w+)", re.IGNORECASE),
    )
    found = build(spec, plsql_lex)("CREATE TABLE t (a NUMBER) WIDGET WIDGET;\n")
    assert [f.object_name for f in found] == ["T", "T"]


def test_table_statement_does_not_let_one_statement_swallow_the_next():
    # DBMS_METADATA.GET_DDL emits no terminating ';', so the bound on an
    # unterminated statement is the next statement's own start; without
    # it the first table would claim the second's clause as well.
    spec = _spec(
        strategy=TABLE_STATEMENT,
        statement_pattern=re.compile(r"\bCREATE\s+TABLE\s+(\w+)", re.IGNORECASE),
    )
    found = build(spec, plsql_lex)(
        "CREATE TABLE t1 (a NUMBER)\nCREATE TABLE t2 (b NUMBER) WIDGET\n"
    )
    assert [f.object_name for f in found] == ["T2"]


def test_statement_clause_reports_each_statement_at_most_once():
    # A second match restates the same fact about the same statement.
    spec = _spec(
        strategy=STATEMENT_CLAUSE,
        statement_pattern=re.compile(r"\bCREATE\s+TABLE\s+(\w+)", re.IGNORECASE),
    )
    found = build(spec, plsql_lex)("CREATE TABLE t (a NUMBER) WIDGET WIDGET;\n")
    assert [f.object_name for f in found] == ["T"]


def test_statement_clause_points_at_the_clause_not_the_statement():
    spec = _spec(
        strategy=STATEMENT_CLAUSE,
        statement_pattern=re.compile(r"\bCREATE\s+TABLE\s+(\w+)", re.IGNORECASE),
    )
    found = build(spec, plsql_lex)("CREATE TABLE t (\n  a NUMBER\n)\nWIDGET;\n")
    assert [f.line for f in found] == [4]


def test_statement_clause_skips_a_statement_without_the_clause():
    spec = _spec(
        strategy=STATEMENT_CLAUSE,
        statement_pattern=re.compile(r"\bCREATE\s+TABLE\s+(\w+)", re.IGNORECASE),
    )
    found = build(spec, plsql_lex)(
        "CREATE TABLE plain (a NUMBER);\nCREATE TABLE odd (b NUMBER) WIDGET;\n"
    )
    assert [f.object_name for f in found] == ["ODD"]


# --- the two views ------------------------------------------------------


def test_by_default_a_construct_inside_dynamic_sql_is_not_searched():
    source = "CREATE PROCEDURE p AS BEGIN EXECUTE IMMEDIATE 'widget'; END;\n"
    assert build(_spec(), plsql_lex)(source) == []


def test_search_mask_can_reach_inside_a_dynamic_sql_literal():
    source = "CREATE PROCEDURE p AS BEGIN EXECUTE IMMEDIATE 'widget'; END;\n"
    found = build(_spec(search_mask=MASK_DYNAMIC_SQL_VISIBLE), plsql_lex)(source)
    assert len(found) == 1
    # Anchored in the fully masked view, which is the one that indexes
    # routine names -- the finding still has to name the routine and line
    # a reader will actually find in the file.
    assert (found[0].object_name, found[0].line) == ("P", 1)


# --- snippets -----------------------------------------------------------


def test_a_callable_snippet_is_computed_from_the_match():
    found = build(
        _spec(
            pattern=re.compile(r"\bWIDGET\s+(\w+)", re.IGNORECASE),
            snippet=lambda m: m.group(1).upper(),
        ),
        plsql_lex,
    )("CREATE PROCEDURE p AS BEGIN widget sprocket; END;\n")
    assert [f.snippet for f in found] == ["SPROCKET"]
