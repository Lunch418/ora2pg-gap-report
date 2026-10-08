from pathlib import Path

from ora2pg_gap_report.detectors.package_type_reference import find_package_type_reference

FIXTURES = Path(__file__).parent / "fixtures" / "gaps_120_123"


def _found(source):
    return [(f.object_name, f.line, f.snippet) for f in find_package_type_reference(source)]


def test_bare_uses_of_package_types_are_flagged_once_per_type():
    assert _found((FIXTURES / "calls_source.sql").read_text(encoding="utf-8")) == [
        ("GX_T_PKG.CODE_OF", 5, "t_code"),
        ("GX_T_PKG.PAIR_SUM", 17, "pair_rt"),
        ("GX_T_PKG.TAB_COUNT", 24, "num_tt"),
    ]


def test_parameters_and_return_types_count():
    source = """CREATE OR REPLACE PACKAGE p AS
  TYPE r_t IS RECORD (a NUMBER);
  FUNCTION f RETURN r_t;
END p;
/
CREATE OR REPLACE PACKAGE q AS
  SUBTYPE s_t IS VARCHAR2(10);
  PROCEDURE g(p_x IN OUT NOCOPY s_t);
END q;
/
"""
    assert _found(source) == [("P.F", 3, "r_t"), ("Q.G", 8, "s_t")]


def test_qualified_uses_ref_cursors_other_packages_and_type_declarations_are_not_flagged():
    source = """CREATE OR REPLACE PACKAGE p AS
  SUBTYPE t_code IS VARCHAR2(10);
  TYPE cur_t IS REF CURSOR;
  TYPE tab_t IS TABLE OF t_code;
  FUNCTION q(a IN p.t_code) RETURN p.t_code;
  FUNCTION c RETURN cur_t;
END p;
/
CREATE OR REPLACE PACKAGE other AS
  FUNCTION z(a IN t_code) RETURN NUMBER;
END other;
/
"""
    assert _found(source) == []


def test_a_body_without_its_spec_knows_no_types():
    source = """CREATE OR REPLACE PACKAGE BODY p AS
  FUNCTION f RETURN r_t IS v r_t; BEGIN RETURN v; END;
END p;
/
"""
    assert _found(source) == []
