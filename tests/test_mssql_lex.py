"""Direct unit tests for the MSSQL-dialect lexer's line_at().

Everything else in mssql_lex.py is exercised indirectly through its
detectors' own tests; line_at() gets a direct test here for the same
reason plsql_lex.py's and mysql_lex.py's do -- see A-03 in the audit this
fixes (a quadratic text.count() call, byte-identical across all three
lexers)."""

from ora2pg_gap_report.mssql_lex import _line_starts, line_at


def test_line_at_matches_a_naive_reference_across_many_positions():
    source = "line1\nline2\n\nline4\nline5"
    for pos in range(len(source) + 1):
        assert line_at(source, pos) == source.count("\n", 0, pos) + 1


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
