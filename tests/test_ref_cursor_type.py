from ora2pg_gap_report.detectors.ref_cursor_type import find_ref_cursor_type


def test_weak_and_strong_ref_cursor_types_are_flagged():
    source = """CREATE OR REPLACE PACKAGE emp_api AS
  TYPE emp_cur IS REF CURSOR;
  TYPE emp_strong_cur IS REF CURSOR RETURN employees%ROWTYPE;
  FUNCTION list_all RETURN emp_cur;
END emp_api;
/
"""
    assert [(f.object_name, f.line) for f in find_ref_cursor_type(source)] == [
        ("EMP_API.EMP_CUR", 2),
        ("EMP_API.EMP_STRONG_CUR", 3),
    ]


def test_the_real_hierarchy_sample_is_flagged():
    from pathlib import Path

    sample = Path(__file__).parents[1] / "docs" / "research" / "samples" / "connect_by_hierarchy_pkg.sql"
    assert [f.snippet for f in find_ref_cursor_type(sample.read_text(encoding="utf-8"))] == [
        "TYPE refcursor IS REF CURSOR"
    ]


def test_sys_refcursor_and_other_types_are_not_flagged():
    source = """CREATE OR REPLACE PACKAGE p AS
  TYPE t_ids IS TABLE OF NUMBER;
  FUNCTION f RETURN SYS_REFCURSOR;
  -- TYPE x IS REF CURSOR;
  c_text CONSTANT VARCHAR2(40) := 'TYPE y IS REF CURSOR';
END p;
/
"""
    assert find_ref_cursor_type(source) == []
