from ora2pg_gap_report.detectors.accessible_by import find_accessible_by


def test_accessible_by_is_flagged_on_a_procedure():
    source = (
        "CREATE OR REPLACE PROCEDURE secret_proc (p_id NUMBER)\n"
        "  ACCESSIBLE BY (PACKAGE hr_admin_pkg)\n"
        "IS\n"
        "BEGIN\n"
        "  UPDATE employees SET salary = salary * 1.1 WHERE employee_id = p_id;\n"
        "END;\n"
        "/\n"
    )
    findings = find_accessible_by(source)
    assert len(findings) == 1
    assert findings[0].object_name == "SECRET_PROC"
    assert findings[0].snippet == "ACCESSIBLE BY"
    assert findings[0].severity == "high"
    assert findings[0].line == 2


def test_accessible_by_with_multiple_accessors_is_flagged_once():
    source = (
        "create or replace function calc (p number) return number\n"
        "  accessible by (package pkg_a, procedure proc_b, function fn_c)\n"
        "is begin return p; end;\n"
        "/\n"
    )
    findings = find_accessible_by(source)
    assert len(findings) == 1
    assert findings[0].object_name == "CALC"


def test_ordinary_subprogram_without_the_clause_is_not_flagged():
    source = (
        "CREATE OR REPLACE PROCEDURE open_proc (p_id NUMBER) IS\n"
        "BEGIN\n"
        "  NULL;\n"
        "END;\n"
        "/\n"
    )
    assert find_accessible_by(source) == []


def test_the_words_in_a_comment_are_not_flagged():
    source = (
        "-- this routine is ACCESSIBLE BY (everyone) per the old design note\n"
        "CREATE OR REPLACE PROCEDURE p IS BEGIN NULL; END;\n"
        "/\n"
    )
    assert find_accessible_by(source) == []
