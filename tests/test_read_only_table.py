from ora2pg_gap_report.detectors.read_only_table import find_read_only_tables


def test_read_only_table_is_flagged():
    source = "create table audit_log (log_id number, message varchar2(200)) read only;\n"
    findings = find_read_only_tables(source)
    assert len(findings) == 1
    assert findings[0].object_name == "AUDIT_LOG"
    assert findings[0].severity == "high"


def test_ordinary_writable_table_is_not_flagged():
    source = "create table orders (order_id number);\n"
    assert find_read_only_tables(source) == []


def test_column_literally_named_read_only_is_not_a_false_positive():
    # 'read_only' as a single identifier (a boolean flag column, a common
    # real-world name) must not match -- there's no whitespace between
    # READ and ONLY there, unlike the real trailing clause.
    source = "create table settings (id number, read_only number(1));\n"
    assert find_read_only_tables(source) == []


def test_read_only_is_not_misattributed_to_a_later_unrelated_table():
    source = (
        "create table snapshot_a (id number) read only;\n"
        "create table live_b (id number);\n"
    )
    findings = find_read_only_tables(source)
    assert len(findings) == 1
    assert findings[0].object_name == "SNAPSHOT_A"


def test_unterminated_statement_does_not_bleed_into_an_earlier_table():
    # DBMS_METADATA.GET_DDL's default output (this project's own
    # documented Oracle export mechanism) has no trailing ';' -- scoping
    # "this table's own text" to just "next ';' or end of file" used to
    # let a later table's own READ ONLY clause bleed all the way back to
    # an earlier, unrelated, unterminated table.
    source = (
        "create table small_lookup (id number)\n"
        "create table audit_log (log_id number) read only\n"
    )
    findings = find_read_only_tables(source)
    assert len(findings) == 1
    assert findings[0].object_name == "AUDIT_LOG"


def test_reported_line_is_the_read_only_token_not_the_create_table_line():
    source = (
        "create table audit_log (\n"
        "  log_id number,\n"
        "  message varchar2(200)\n"
        ") read only;\n"
    )
    findings = find_read_only_tables(source)
    assert len(findings) == 1
    assert findings[0].line == 4


def test_double_quoted_column_named_read_only_is_not_a_false_positive():
    # mask_strings_and_comments() only masks single-quoted string
    # literals/comments, never double-quoted identifiers -- a column
    # named "READ ONLY" (valid Oracle identifier syntax) must not be
    # confused with the real trailing clause.
    source = 'create table settings (id number, "READ ONLY" number(1));\n'
    assert find_read_only_tables(source) == []
