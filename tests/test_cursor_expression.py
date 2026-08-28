from ora2pg_gap_report.detectors.cursor_expression import find_cursor_expressions


def test_a_cursor_expression_is_flagged():
    source = (
        "SELECT d.dname,\n"
        "       CURSOR(SELECT e.name FROM employees e WHERE e.dept_id = d.id) AS emps\n"
        "  FROM departments d;\n"
    )
    findings = find_cursor_expressions(source)
    assert len(findings) == 1
    assert findings[0].snippet == "CURSOR(SELECT"
    assert findings[0].severity == "high"
    assert findings[0].line == 2


def test_whitespace_between_the_keyword_and_the_paren_is_tolerated():
    assert len(find_cursor_expressions("SELECT CURSOR ( SELECT 1 FROM dual) FROM dual;\n")) == 1


def test_an_ordinary_cursor_declaration_is_not_flagged():
    # ora2pg converts this correctly -- flagging it would be a false positive.
    source = (
        "DECLARE\n"
        "  CURSOR c IS SELECT emp_id FROM employees;\n"
        "BEGIN\n"
        "  NULL;\n"
        "END;\n"
    )
    assert find_cursor_expressions(source) == []


def test_a_parameterised_cursor_declaration_is_not_flagged():
    source = "DECLARE\n  CURSOR c (p NUMBER) IS SELECT 1 FROM dual;\nBEGIN\n NULL;\nEND;\n"
    assert find_cursor_expressions(source) == []


def test_a_commented_out_cursor_expression_is_not_flagged():
    assert find_cursor_expressions("-- CURSOR(SELECT 1 FROM dual)\nSELECT 1 FROM dual;\n") == []


def test_real_open_source_alexandria_cursor_expression_is_flagged():
    # Real shape from alexandria-plsql-utils
    # (demos/string_util_pkg_demo.sql): a cursor expression passed as a
    # function argument, all lowercase.
    source = (
        "select string_util_pkg.join_str(cursor(select ename from emp order by ename))\n"
        "  from dual;\n"
    )
    findings = find_cursor_expressions(source)
    assert len(findings) == 1
    assert findings[0].line == 1
