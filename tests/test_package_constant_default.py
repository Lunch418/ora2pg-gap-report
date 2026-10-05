from pathlib import Path

from ora2pg_gap_report.detectors.package_constant_default import find_package_constant_default

SAMPLES = Path(__file__).parents[1] / "docs" / "research" / "samples"


def test_a_package_constant_default_is_flagged():
    source = """CREATE OR REPLACE PACKAGE file_pkg AS
  g_os_windows CONSTANT VARCHAR2(1) := 'w';
  FUNCTION sep(p_os IN VARCHAR2 := g_os_windows) RETURN VARCHAR2;
  PROCEDURE q(p_a NUMBER, p_b VARCHAR2 DEFAULT file_pkg.g_os_windows);
END file_pkg;
/
"""
    assert [(f.object_name, f.line, f.snippet) for f in find_package_constant_default(source)] == [
        ("FILE_PKG.SEP", 3, "DEFAULT g_os_windows"),
        ("FILE_PKG.Q", 4, "DEFAULT file_pkg.g_os_windows"),
    ]


def test_the_real_file_util_body_is_flagged_without_its_spec():
    # alexandria-plsql-utils' file_util_pkg: the body alone, as GET_DDL
    # often exports it; the constant lives in the spec.
    source = (SAMPLES / "file_util_pkg.pkb").read_text(encoding="utf-8")
    assert [f.snippet for f in find_package_constant_default(source)] == ["DEFAULT g_os_windows"] * 2


def test_literals_expressions_calls_and_builtins_are_not_flagged():
    source = """CREATE OR REPLACE PACKAGE BODY p AS
  PROCEDURE x(
    a NUMBER := 1,
    b VARCHAR2 DEFAULT 'g_name',
    c DATE := SYSDATE,
    d BOOLEAN := TRUE,
    e NUMBER := NULL,
    f NUMBER := c_base + 1,
    g NUMBER := next_id()
  ) IS
  BEGIN
    NULL;
  END;
END p;
/
"""
    assert find_package_constant_default(source) == []


def test_standalone_routines_are_not_this_gap():
    source = "CREATE OR REPLACE PROCEDURE x(p VARCHAR2 := g_name) IS BEGIN NULL; END;\n/\n"
    assert find_package_constant_default(source) == []
