from pathlib import Path

from ora2pg_gap_report.detectors.schema_qualified_name import find_schema_qualified_name

FIXTURES = Path(__file__).parent / "fixtures" / "gaps_124_125"


def _found(source):
    return [(f.object_name, f.line, f.snippet) for f in find_schema_qualified_name(source)]


def test_get_ddl_names_are_flagged_once_per_schema():
    assert _found((FIXTURES / "oracle_source.sql").read_text(encoding="utf-8")) == [("HR.GX_EMP", 1, '"HR"."GX_EMP"')]


def test_unquoted_and_other_object_kinds():
    source = (
        "CREATE SEQUENCE app.s1;\n"
        "CREATE OR REPLACE FORCE NONEDITIONABLE VIEW rep.v AS SELECT 1 x FROM dual;\n"
        "CREATE GLOBAL TEMPORARY TABLE app.tmp (id NUMBER);\n"
    )
    assert _found(source) == [("APP.S1", 1, "app.s1"), ("REP.V", 2, "rep.v")]


def test_unqualified_names_packages_and_schemas_the_file_creates_are_not_flagged():
    source = (
        "CREATE TABLE emp (id NUMBER);\n"
        'CREATE OR REPLACE EDITIONABLE PACKAGE "HR"."P" AS PROCEDURE x; END;\n/\n'
        "-- CREATE TABLE hr.commented (id NUMBER);\n"
        "INSERT INTO hr.emp VALUES ('CREATE TABLE hr.in_a_string');\n"
    )
    assert _found(source) == []
    # ora2pg's own output: a package becomes a schema it creates
    output = (FIXTURES / "oracle_PACKAGE_output.sql").read_text(encoding="utf-8")
    assert "CREATE OR REPLACE FUNCTION gx_pkg.f" in output and _found(output) == []
