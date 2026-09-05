"""Direct unit tests for the dialect-independent lexer primitives.

These used to live three times over, once per dialect lexer, because the
code did too -- test_mssql_lex.py was nothing but a second copy of
test_plsql_lex.py's line_at() tests, and said so in its own docstring.
Now that the implementation exists once, so does its test.
"""

import pytest

from ora2pg_gap_report.lex_common import (
    _line_starts,
    flat_enclosing_object_name,
    line_at,
    skip_balanced_parens,
    table_column_definition_list,
)


# --- A-03 regression: line_at() must stay O(log n) per call, not O(n). ---


def test_line_at_matches_a_naive_reference_across_many_positions():
    source = "line1\nline2\n\nline4\nline5"
    for pos in range(len(source) + 1):
        assert line_at(source, pos) == source.count("\n", 0, pos) + 1


def test_line_at_on_a_position_at_the_very_start_of_a_line():
    source = "aaa\nbbb\nccc"
    assert line_at(source, source.index("bbb")) == 2


def test_line_at_reuses_the_cached_newline_index_across_calls():
    # The mechanism that keeps a whole scan O(n) rather than O(n^2): one
    # distinct `text` in flight per scan_source() call, however many
    # findings (and therefore however many line_at() lookups) it produces.
    _line_starts.cache_clear()
    source = "a\nb\nc\nd\n" * 50
    for pos in (0, 10, len(source) - 1):
        line_at(source, pos)
    info = _line_starts.cache_info()
    assert info.misses == 1
    assert info.hits == 2


def test_every_dialect_lexer_exposes_the_same_shared_line_at():
    # Each lexer re-exports these rather than defining its own, so a fix
    # to one is a fix to all three -- which is the entire point of the
    # module existing.
    from ora2pg_gap_report import mssql_lex, mysql_lex, plsql_lex

    for lex in (plsql_lex, mysql_lex, mssql_lex):
        assert lex.line_at is line_at
        assert lex.skip_balanced_parens is skip_balanced_parens
        assert lex.table_column_definition_list is table_column_definition_list
    # Oracle needs its own: a routine there can be nested in a package
    # body and has to be reported as PACKAGE.ROUTINE.
    assert mysql_lex.enclosing_object_name is flat_enclosing_object_name
    assert mssql_lex.enclosing_object_name is flat_enclosing_object_name
    assert plsql_lex.enclosing_object_name is not flat_enclosing_object_name


# --- balanced parentheses ------------------------------------------------


def test_skip_balanced_parens_returns_the_index_just_past_the_match():
    text = "f(a, (b, c), d) tail"
    assert text[skip_balanced_parens(text, 1) :] == " tail"


def test_skip_balanced_parens_on_an_unclosed_paren_stops_at_end_of_text():
    # Truncated input is ordinary here (a file cut mid-statement); running
    # off the end is the defined answer, not an exception.
    text = "f(a, b"
    assert skip_balanced_parens(text, 1) == len(text)


# --- the column-definition list -----------------------------------------


def test_table_column_definition_list_spans_the_column_list_only():
    text = "CREATE TABLE t (a NUMBER, b VARCHAR2(10)) TABLESPACE ts;"
    span = table_column_definition_list(text, text.index("t (") + 1)
    assert span is not None
    open_pos, close_pos = span
    assert text[open_pos + 1 : close_pos] == "a NUMBER, b VARCHAR2(10)"


def test_table_column_definition_list_is_none_for_a_bare_ctas():
    # 'CREATE TABLE name AS SELECT ...' has no column-type list at all, so
    # a column-level detector has nothing to search rather than a whole
    # SELECT to misread.
    text = "CREATE TABLE t AS SELECT ROWID rid FROM u;"
    assert table_column_definition_list(text, text.index(" AS")) is None


# --- flat object attribution ---------------------------------------------


@pytest.mark.parametrize(
    ("position", "expected"),
    [(0, "UNKNOWN"), (15, "P1"), (60, "P2")],
)
def test_flat_enclosing_object_name_picks_the_most_recent_container(position, expected):
    index = ((10, "procedure", "P1"), (50, "procedure", "P2"))
    assert flat_enclosing_object_name(index, position) == expected
