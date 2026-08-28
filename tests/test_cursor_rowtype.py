from ora2pg_gap_report.detectors.cursor_rowtype import find_cursor_rowtype


def test_a_rowtype_taken_from_a_cursor_is_flagged():
    source = (
        "CREATE OR REPLACE PROCEDURE walk IS\n"
        "  CURSOR c IS SELECT emp_id, name FROM employees;\n"
        "  r c%ROWTYPE;\n"
        "BEGIN\n"
        "  OPEN c; FETCH c INTO r; CLOSE c;\n"
        "END;\n"
    )
    findings = find_cursor_rowtype(source)
    assert len(findings) == 1
    assert findings[0].object_name == "WALK"
    assert findings[0].snippet == "c%ROWTYPE"
    assert findings[0].severity == "high"
    assert findings[0].line == 3


def test_a_rowtype_taken_from_a_table_is_not_flagged():
    # ora2pg carries `<table>%ROWTYPE` across correctly.
    source = "DECLARE\n  r employees%ROWTYPE;\nBEGIN\n  NULL;\nEND;\n"
    assert find_cursor_rowtype(source) == []


def test_a_table_rowtype_next_to_a_cursor_declaration_is_not_flagged():
    # Only the name that is actually a cursor may be reported.
    source = (
        "DECLARE\n"
        "  CURSOR c IS SELECT 1 FROM dual;\n"
        "  r employees%ROWTYPE;\n"
        "BEGIN\n"
        "  NULL;\n"
        "END;\n"
    )
    assert find_cursor_rowtype(source) == []


def test_a_qualified_table_rowtype_is_not_flagged():
    source = "DECLARE\n  CURSOR c IS SELECT 1 FROM dual;\n  r hr.c%ROWTYPE;\nBEGIN\n NULL;\nEND;\n"
    assert find_cursor_rowtype(source) == []


def test_a_source_with_no_cursor_at_all_is_cheap_and_clean():
    assert find_cursor_rowtype("DECLARE\n  r t%ROWTYPE;\nBEGIN\n NULL;\nEND;\n") == []


def test_a_parameterised_cursor_is_recognised():
    source = (
        "DECLARE\n"
        "  CURSOR c (p NUMBER) IS SELECT 1 FROM dual;\n"
        "  r c%ROWTYPE;\n"
        "BEGIN\n"
        "  NULL;\n"
        "END;\n"
    )
    assert len(find_cursor_rowtype(source)) == 1


def test_real_open_source_utplsql_cursor_rowtype_is_flagged():
    # Real shape from utPLSQL (source/core/ut_suite_manager.pkb around
    # line 20): a cursor declared on one line and used as the element type
    # of two separate declarations right below it.
    source = (
        "  gc_suitpath_error_message constant varchar2(100) := 'Suitepath exceeds 1000 CHAR on: ';\n"
        "  cursor c_cached_suites_cursor is select * from table(ut_suite_cache_rows());\n"
        "  type tt_cached_suites         is table of c_cached_suites_cursor%rowtype;\n"
        "  type t_cached_suites_cursor   is ref cursor return c_cached_suites_cursor%rowtype;\n"
    )
    findings = find_cursor_rowtype(source)
    assert len(findings) == 2
    assert [f.line for f in findings] == [3, 4]
