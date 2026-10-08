from pathlib import Path

from ora2pg_gap_report.detectors.package_type_anchor import find_package_type_anchor

FIXTURES = Path(__file__).parent / "fixtures" / "gaps_120_123"
SAMPLES = Path(__file__).parents[1] / "docs" / "research" / "samples"


def _found(source):
    return [(f.object_name, f.line, f.snippet) for f in find_package_type_anchor(source)]


def test_record_fields_and_subtypes_anchored_with_type_are_flagged():
    assert _found((FIXTURES / "types_source.sql").read_text(encoding="utf-8")) == [
        ("GX_REC_PKG", 7, "TYPE emp_rt IS RECORD (... %TYPE)"),
        ("GX_REC_PKG", 11, "SUBTYPE t_name IS g_name_def%TYPE"),
        ("GX_REC_PKG", 12, "SUBTYPE t_sal IS gx_emp.salary%TYPE"),
    ]


def test_rowtype_is_flagged_too():
    assert [s for _, _, s in _found((FIXTURES / "edge_source.sql").read_text(encoding="utf-8"))] == [
        "SUBTYPE t_emp IS gx_emp%ROWTYPE",
        "TYPE emp2_rt IS RECORD (... %ROWTYPE)",
    ]


def test_the_real_samples():
    assert len(_found((SAMPLES / "file_util_pkg.pks").read_text(encoding="utf-8"))) == 3
    assert len(_found((SAMPLES / "logger.pks").read_text(encoding="utf-8"))) == 1


def test_plain_types_and_routine_level_declarations_are_not_flagged():
    source = """CREATE OR REPLACE PACKAGE p AS
  SUBTYPE t_code IS VARCHAR2(10);
  TYPE pair_rt IS RECORD (a NUMBER(6), b VARCHAR2(10));
  -- TYPE c_rt IS RECORD (x t.c%TYPE);
END p;
/
CREATE OR REPLACE PACKAGE BODY p AS
  PROCEDURE x IS
    TYPE local_rt IS RECORD (a emp.salary%TYPE);
    SUBTYPE t_local IS emp.salary%TYPE;
    v emp.salary%TYPE;
  BEGIN
    NULL;
  END;
END p;
/
CREATE OR REPLACE PROCEDURE q IS
  TYPE r IS RECORD (a emp.salary%TYPE);
BEGIN
  NULL;
END;
/
"""
    assert _found(source) == []
