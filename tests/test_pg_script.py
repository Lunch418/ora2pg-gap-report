from ora2pg_gap_report.pg_script import parse_script, sanitize


def _keywords(source):
    return [s.keywords for s in parse_script(source).statements]


def test_statements_end_at_top_level_semicolons_only():
    source = "SELECT 'a;b', \"x;y\", (1;2);\nSELECT 2;\n"
    parsed = parse_script(source)
    assert [(s.start_line, s.end_line) for s in parsed.statements] == [(1, 1), (2, 2)]


def test_dollar_quoted_body_is_one_statement():
    source = (
        "CREATE FUNCTION f() RETURNS int AS $body$\n"
        "BEGIN\n"
        "  RETURN 1;\n"
        "END;\n"
        "$body$ LANGUAGE plpgsql;\n"
        "SELECT 1;\n"
    )
    parsed = parse_script(source)
    assert [(s.start_line, s.end_line) for s in parsed.statements] == [(1, 5), (6, 6)]


def test_dollar_sign_inside_identifier_or_parameter_is_not_a_quote():
    # `a$b$` is an identifier and `$1` a parameter; neither opens a quote.
    source = "SELECT a$b$ FROM t WHERE x = $1;\nSELECT 2;\n"
    assert len(parse_script(source).statements) == 2


def test_nested_block_comments_and_line_comments_hide_semicolons():
    source = "/* a /* b; */ c; */ SELECT 1 -- x; y\n;\nSELECT 2;\n"
    parsed = parse_script(source)
    assert [s.keywords[:1] for s in parsed.statements] == [("SELECT",), ("SELECT",)]
    assert parsed.statements[0].end_line == 2


def test_escape_string_with_backslash_quote():
    source = "SELECT E'it\\'s; fine';\nSELECT 2;\n"
    assert len(parse_script(source).statements) == 2


def test_statement_starts_after_leading_comments_and_blank_lines():
    source = "-- header\n\n\nCREATE TABLE t (\n  id int\n);\n"
    (statement,) = parse_script(source).statements
    assert (statement.start_line, statement.end_line) == (4, 6)


def test_meta_commands_are_collected_with_their_line():
    source = "SET x = 1;\n\\set ON_ERROR_STOP ON\n\\i other.sql\nSELECT 1;\n"
    parsed = parse_script(source)
    assert [(m.line, m.text) for m in parsed.meta_commands] == [
        (2, "\\set ON_ERROR_STOP ON"),
        (3, "\\i other.sql"),
    ]
    assert len(parsed.statements) == 2


def test_unterminated_last_statement_is_still_a_statement():
    # psql sends what is left at the end of an \i'd file.
    parsed = parse_script("SELECT 1;\nSELECT 2")
    assert len(parsed.statements) == 2
    assert parsed.unterminated is None


def test_unclosed_quote_or_dollar_quote_is_reported():
    quote = parse_script("SELECT 1;\nSELECT 'oops;\n")
    assert (quote.unterminated, quote.unterminated_line) == ("quote", 2)
    dollar = parse_script("CREATE FUNCTION f() AS $$\nBEGIN\n")
    assert (dollar.unterminated, dollar.unterminated_line) == ("dollar_quote", 1)
    comment = parse_script("/* never closed\n")
    assert comment.unterminated == "comment"


def test_sanitize_blanks_what_would_defeat_the_check_and_keeps_line_numbers():
    source = (
        "SET client_encoding TO 'UTF8';\r\n"
        "\\set ON_ERROR_STOP ON\r\n"
        "SET check_function_bodies = false;\r\n"
        "BEGIN;\r\n"
        "CREATE TABLE t (id int);\r\n"
        "COMMIT;\r\n"
        "END;\r\n"
        "START TRANSACTION;\r\n"
        "SET LOCAL check_function_bodies TO off;\r\n"
    )
    clean, removed = sanitize(source)
    assert len(clean) == len(source)
    assert clean.splitlines(keepends=True)[4] == "CREATE TABLE t (id int);\r\n"
    assert clean.count("\r\n") == source.count("\r\n")
    for gone in ("ON_ERROR_STOP", "check_function_bodies", "BEGIN", "COMMIT", "END;", "START"):
        assert gone not in clean
    assert "client_encoding" in clean
    assert [(r.line, r.kind) for r in removed] == [
        (2, "meta"),
        (3, "setting"),
        (4, "transaction"),
        (6, "transaction"),
        (7, "transaction"),
        (8, "transaction"),
        (9, "setting"),
    ]


def test_sanitize_leaves_plpgsql_begin_and_commit_inside_bodies_alone():
    source = (
        "CREATE PROCEDURE p() AS $$\n"
        "BEGIN\n"
        "  COMMIT;\n"
        "END;\n"
        "$$ LANGUAGE plpgsql;\n"
    )
    clean, removed = sanitize(source)
    assert clean == source
    assert removed == []


def test_sanitize_keeps_non_utf8_bytes_through_surrogateescape():
    raw = "-- комментарий\nSELECT 1;\n".encode("cp1251")
    source = raw.decode("utf-8", errors="surrogateescape")
    clean, _ = sanitize(source)
    assert clean.encode("utf-8", errors="surrogateescape") == raw


def test_leading_keywords_are_uppercased():
    assert _keywords("create or replace view v as select 1;") == [("CREATE", "OR", "REPLACE")]
