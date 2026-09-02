"""Direct unit tests for the MySQL-dialect lexer.

Unlike plsql_lex.py (exercised indirectly by every one of its 67
detectors' own tests, with test_plsql_lex.py covering only bugs found in
code review), mysql_lex.py has no detectors built on it yet -- so its
masking/attribution contract is tested directly here instead of only
through downstream detector behavior."""

from ora2pg_gap_report.mysql_lex import (
    _line_starts,
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_comments_only,
    mask_strings_and_comments,
    qualified_name_pattern,
    table_column_definition_list,
)


def test_masking_preserves_length_and_newlines():
    source = "CREATE TABLE t (\n  a INT, -- x\n  b INT # y\n);\n"
    masked = mask_strings_and_comments(source)
    assert len(masked) == len(source)
    assert masked.count("\n") == source.count("\n")


def test_double_dash_comment_requires_trailing_whitespace():
    # MySQL's actual rule: '--' only starts a comment when followed by
    # whitespace/control. 'a--b' is subtraction, not a comment -- and if
    # masking got this wrong, the rest of the line ('b') would be wiped
    # out as if it were commented-out code.
    source = "SELECT a--b FROM t;\n"
    masked = mask_strings_and_comments(source)
    assert "b FROM t" in masked


def test_double_dash_with_trailing_space_is_a_real_comment():
    source = "SELECT 1 -- BEGIN this is a comment\nFROM t;\n"
    masked = mask_strings_and_comments(source)
    assert "BEGIN" not in masked
    assert "FROM t" in masked


def test_hash_comment_is_masked():
    source = "SELECT 1 # PRAGMA-looking text\nFROM t;\n"
    masked = mask_strings_and_comments(source)
    assert "PRAGMA" not in masked
    assert "FROM t" in masked


def test_block_comment_is_masked():
    source = "SELECT /* CREATE TRIGGER inside a comment */ 1 FROM t;\n"
    masked = mask_strings_and_comments(source)
    assert "CREATE TRIGGER" not in masked
    assert "FROM t" in masked


def test_single_and_double_quoted_strings_are_both_masked():
    source = "SELECT 'BEGIN one', \"BEGIN two\" FROM t;\n"
    masked = mask_strings_and_comments(source)
    assert "BEGIN one" not in masked
    assert "BEGIN two" not in masked
    assert "FROM t" in masked


def test_backslash_escape_inside_a_string_does_not_end_it_early():
    # Non-standard-SQL MySQL rule: backslash escapes the next character,
    # so \' inside a '...'-quoted string is an escaped apostrophe, not
    # the string's own closing quote.
    source = "SELECT 'it\\'s a test' FROM t;\n"
    masked = mask_strings_and_comments(source)
    assert "FROM t" in masked
    # The masked view blanks quote delimiters too (matching plsql_lex's own
    # masked view -- see its "'" if reveal else " " branch), so a correctly
    # masked string leaves zero quote characters, not two. If backslash
    # escaping were broken, the literal would end early at \', and " FROM
    # t;\n" would then be swallowed as the *next* string literal's content
    # instead -- which is exactly what the "FROM t" in masked check above
    # would catch.
    assert masked.count("'") == 0


def test_doubled_quote_escape_inside_a_string_does_not_end_it_early():
    source = "SELECT 'it''s a test' FROM t;\n"
    masked = mask_strings_and_comments(source)
    assert "FROM t" in masked
    assert masked.count("'") == 0


def test_comment_markers_inside_a_string_literal_are_not_comments():
    source = "UPDATE t SET note = 'x--y # z /* not a comment */' WHERE id = 1;\n"
    masked = mask_strings_and_comments(source)
    assert "WHERE id = 1" in masked


def test_backtick_quoted_identifier_survives_masking_untouched():
    source = "SELECT `end`, `weird--col` FROM `orders`;\n"
    masked = mask_strings_and_comments(source)
    assert "`end`" in masked
    assert "`weird--col`" in masked
    assert "`orders`" in masked


def test_doubled_backtick_escapes_a_literal_backtick_in_a_name():
    source = "SELECT `a``b` FROM t;\n"
    masked = mask_strings_and_comments(source)
    assert "FROM t" in masked
    assert masked.count("`") == 4  # the whole `a``b` span survives as-is


def test_mask_comments_only_keeps_string_and_backtick_content():
    source = "SELECT 'BEGIN kept', `end` -- but this is gone\nFROM t;\n"
    revealed = mask_comments_only(source)
    assert "BEGIN kept" in revealed
    assert "`end`" in revealed
    assert "but this is gone" not in revealed
    assert len(revealed) == len(source)


def test_object_index_recognizes_all_five_container_kinds():
    source = (
        "CREATE TABLE t1 (id INT);\n"
        "CREATE PROCEDURE p1() BEGIN SELECT 1; END;\n"
        "CREATE FUNCTION f1() RETURNS INT RETURN 1;\n"
        "CREATE TRIGGER tr1 BEFORE INSERT ON t1 FOR EACH ROW SET NEW.id = 1;\n"
        "CREATE VIEW v1 AS SELECT * FROM t1;\n"
    )
    masked = mask_strings_and_comments(source)
    idx = enclosing_object_name_index(masked)
    kinds_and_names = {(kind, name) for _, kind, name in idx}
    assert kinds_and_names == {
        ("table", "T1"),
        ("procedure", "P1"),
        ("function", "F1"),
        ("trigger", "TR1"),
        ("view", "V1"),
    }


def test_object_index_reads_a_backtick_quoted_name():
    source = "CREATE TABLE `orders` (id INT);\n"
    masked = mask_strings_and_comments(source)
    idx = enclosing_object_name_index(masked)
    assert idx[0][1:] == ("table", "ORDERS")


def test_enclosing_object_name_attributes_to_the_nearest_preceding_container():
    source = (
        "CREATE TABLE t1 (id INT);\n"
        "CREATE PROCEDURE charge(IN p_id INT)\n"
        "BEGIN\n"
        "  UPDATE t1 SET id = p_id;\n"
        "END;\n"
    )
    masked = mask_strings_and_comments(source)
    idx = enclosing_object_name_index(masked)
    update_pos = source.index("UPDATE t1")
    assert enclosing_object_name(idx, update_pos) == "CHARGE"


def test_enclosing_object_name_is_unknown_before_any_container():
    assert enclosing_object_name((), 0) == "UNKNOWN"


def test_table_column_definition_list_scopes_to_the_paren_span():
    source = "CREATE TABLE t (a INT, b VARCHAR(10)) ENGINE=InnoDB;\n"
    masked = mask_strings_and_comments(source)
    name_end = source.index("t (") + 1
    span = table_column_definition_list(masked, name_end)
    assert span is not None
    open_pos, close_pos = span
    assert masked[open_pos] == "("
    assert masked[close_pos] == ")"
    assert "ENGINE" not in masked[open_pos:close_pos]


def test_table_column_definition_list_returns_none_for_a_bare_ctas():
    source = "CREATE TABLE t AS SELECT * FROM other;\n"
    masked = mask_strings_and_comments(source)
    name_end = source.index("t AS") + 1
    assert table_column_definition_list(masked, name_end) is None


def test_qualified_name_pattern_matches_a_schema_qualified_backtick_name():
    import re

    pattern = re.compile(qualified_name_pattern(r"CREATE\s+TABLE"), re.IGNORECASE)
    m = pattern.search("CREATE TABLE `mydb`.`orders` (id INT);")
    assert m is not None
    assert m.group(1) == "orders"


# --- A-03 regression: line_at() must stay O(log n) per call, not O(n). ---


def test_line_at_matches_a_naive_reference_across_many_positions():
    source = "line1\nline2\n\nline4\nline5"
    for pos in range(len(source) + 1):
        assert line_at(source, pos) == source.count("\n", 0, pos) + 1


def test_line_at_reuses_the_cached_newline_index_across_calls():
    _line_starts.cache_clear()
    source = "a\nb\nc\nd\n" * 50
    for pos in (0, 10, len(source) - 1):
        line_at(source, pos)
    info = _line_starts.cache_info()
    assert info.misses == 1
    assert info.hits == 2
