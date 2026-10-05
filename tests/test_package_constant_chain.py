from ora2pg_gap_report.detectors.package_constant_chain import find_package_constant_chain

PACKAGE = """CREATE OR REPLACE PACKAGE BODY fmt_pkg AS
  c_date CONSTANT VARCHAR2(30) := 'YYYY-MM-DD';
  c_stamp CONSTANT VARCHAR2(30) := c_date || ' HH24:MI';
  c_plain CONSTANT VARCHAR2(30) := 'HH24';

  FUNCTION stamp_fmt RETURN VARCHAR2 IS
    l_local VARCHAR2(30) := c_date || 'x';
  BEGIN
    RETURN c_stamp;
  END;
END fmt_pkg;
/
"""


def test_a_constant_built_from_another_is_flagged():
    # The minimal case confirmed with ora2pg 25.0 and PostgreSQL 16.
    assert [(f.object_name, f.line, f.snippet) for f in find_package_constant_chain(PACKAGE)] == [
        ("FMT_PKG.C_STAMP", 3, "c_stamp := ... c_date ...")
    ]


def test_the_real_logger_package_has_two():
    # OraOpenSource Logger, where --load-check first showed the breakage.
    from pathlib import Path

    source = (Path(__file__).parents[1] / "docs" / "research" / "samples" / "logger.pkb").read_text(encoding="utf-8")
    assert [f.object_name for f in find_package_constant_chain(source)] == [
        "LOGGER.GC_TIMESTAMP_FORMAT",
        "LOGGER.GC_TIMESTAMP_TZ_FORMAT",
    ]


def test_literal_initializers_and_routine_locals_are_not_flagged():
    source = """CREATE OR REPLACE PACKAGE BODY p AS
  c_a CONSTANT NUMBER := 1;
  c_b CONSTANT NUMBER := 2 + 3;
  PROCEDURE x IS
    l_c NUMBER := c_a + 1;
  BEGIN
    NULL;
  END;
END p;
/
"""
    assert find_package_constant_chain(source) == []


def test_a_name_inside_a_string_or_a_longer_name_is_not_a_reference():
    source = """CREATE OR REPLACE PACKAGE p AS
  c_a CONSTANT VARCHAR2(9) := 'x';
  c_b CONSTANT VARCHAR2(9) := 'c_a';
  c_c CONSTANT VARCHAR2(9) := c_a_other;
END p;
/
"""
    assert find_package_constant_chain(source) == []


def test_the_spec_is_read_too():
    source = """CREATE OR REPLACE PACKAGE p AS
  c_a CONSTANT NUMBER := 1;
  c_b CONSTANT NUMBER := c_a * 2;
  FUNCTION f RETURN NUMBER;
END p;
/
"""
    assert [f.object_name for f in find_package_constant_chain(source)] == ["P.C_B"]
