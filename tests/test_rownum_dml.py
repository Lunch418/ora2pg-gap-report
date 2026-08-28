from ora2pg_gap_report.detectors.rownum_dml import find_rownum_dml


def test_rownum_in_an_update_is_flagged():
    source = "UPDATE employees SET bonus = 0 WHERE ROWNUM <= 10;\n"
    findings = find_rownum_dml(source)
    assert len(findings) == 1
    assert findings[0].snippet == "UPDATE ... ROWNUM"
    assert findings[0].severity == "high"


def test_rownum_in_a_delete_is_flagged():
    findings = find_rownum_dml("DELETE FROM employees WHERE ROWNUM <= 5;\n")
    assert len(findings) == 1
    assert findings[0].snippet == "DELETE ... ROWNUM"


def test_rownum_in_a_plain_select_is_not_flagged():
    # ora2pg turns this into a valid `LIMIT n` on a SELECT.
    assert find_rownum_dml("SELECT * FROM employees WHERE ROWNUM <= 10;\n") == []


def test_rownum_in_a_subquery_of_a_delete_is_not_flagged():
    # Verified against real ora2pg + PostgreSQL: this converts to a
    # subquery LIMIT and runs correctly, so flagging it would be a false
    # positive. See docs/research/gap-057-rownum-dml.md.
    source = (
        "DELETE FROM employees WHERE emp_id IN "
        "(SELECT emp_id FROM staff WHERE ROWNUM <= 5);\n"
    )
    assert find_rownum_dml(source) == []


def test_rownum_in_a_scalar_subquery_of_an_update_is_not_flagged():
    source = (
        "UPDATE employees e SET mgr = "
        "(SELECT id FROM staff WHERE ROWNUM = 1);\n"
    )
    assert find_rownum_dml(source) == []


def test_a_statement_without_rownum_is_not_flagged():
    assert find_rownum_dml("UPDATE employees SET bonus = 0 WHERE dept = 3;\n") == []


def test_rownum_inside_a_comment_is_not_flagged():
    assert find_rownum_dml("UPDATE t SET a = 1; -- used to say WHERE ROWNUM <= 5\n") == []
