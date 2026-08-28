from ora2pg_gap_report.detectors.goto_statement import find_goto_statements


def test_a_goto_statement_is_flagged():
    source = (
        "CREATE OR REPLACE PROCEDURE hop IS\n"
        "  i NUMBER := 0;\n"
        "BEGIN\n"
        "  <<again>>\n"
        "  i := i + 1;\n"
        "  IF i < 3 THEN\n"
        "    GOTO again;\n"
        "  END IF;\n"
        "END;\n"
    )
    findings = find_goto_statements(source)
    assert len(findings) == 1
    assert findings[0].object_name == "HOP"
    assert findings[0].snippet == "GOTO again"
    assert findings[0].severity == "high"
    assert findings[0].line == 7


def test_several_jumps_are_reported_separately():
    source = "BEGIN\n  GOTO one;\n  GOTO two;\nEND;\n"
    assert len(find_goto_statements(source)) == 2


def test_a_label_on_its_own_is_not_flagged():
    # PL/pgSQL accepts block labels; only the jump is the problem.
    assert find_goto_statements("BEGIN\n  <<again>>\n  NULL;\nEND;\n") == []


def test_a_column_named_goto_is_not_flagged():
    assert find_goto_statements("SELECT goto_url FROM links;\n") == []


def test_a_commented_out_jump_is_not_flagged():
    assert find_goto_statements("BEGIN\n  -- GOTO again;\n  NULL;\nEND;\n") == []


def test_real_open_source_alexandria_goto_is_flagged():
    # Real shape from alexandria-plsql-utils (ora/csv_util_pkg.pkb): a
    # backward jump to a loop label, the classic case that becomes
    # LOOP/CONTINUE in PL/pgSQL.
    source = (
        "    <<loop_again>>\n"
        "    l_pos := l_pos + 1;\n"
        "    if l_pos < l_len then\n"
        "      goto loop_again;\n"
        "    end if;\n"
    )
    findings = find_goto_statements(source)
    assert len(findings) == 1
    assert findings[0].snippet == "GOTO loop_again"
    assert findings[0].line == 4
