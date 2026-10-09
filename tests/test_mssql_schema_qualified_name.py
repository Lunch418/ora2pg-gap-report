from pathlib import Path

from ora2pg_gap_report.autofix import fix_mssql_missing_schema
from ora2pg_gap_report.detectors.mssql_schema_qualified_name import find_mssql_schema_qualified_name

FIXTURES = Path(__file__).parent / "fixtures" / "gaps_124_125"


def _found(source):
    return [(f.object_name, f.line, f.snippet) for f in find_mssql_schema_qualified_name(source)]


def test_ssms_names_are_flagged_once_per_schema():
    assert _found((FIXTURES / "mssql_source.sql").read_text(encoding="utf-8")) == [("dbo.Orders", 1, "[dbo].[Orders]")]


def test_bare_and_three_part_names():
    source = "CREATE PROC sales.p AS SELECT 1\nGO\nCREATE OR ALTER VIEW Shop.[hr].[v] AS SELECT 1 AS x\nGO\n"
    assert _found(source) == [("sales.p", 1, "sales.p"), ("hr.v", 3, "[hr].[v]")]


def test_unqualified_names_and_created_schemas_are_not_flagged():
    source = "CREATE SCHEMA [app]\nGO\nCREATE TABLE [app].[t] (id int)\nGO\nCREATE TABLE [u] (id int)\nGO\n"
    assert _found(source) == []


def test_fix_creates_each_missing_schema_once_after_the_header():
    output = (FIXTURES / "mssql_TABLE_output.sql").read_text(encoding="utf-8")
    fixed, count = fix_mssql_missing_schema(output)
    assert count == 1
    lines = fixed.splitlines()
    at = lines.index("CREATE SCHEMA IF NOT EXISTS dbo;")
    assert lines[at - 1].startswith("\\set ON_ERROR_STOP")
    assert at < next(i for i, line in enumerate(lines) if line.startswith("CREATE TABLE dbo.orders"))
    assert fix_mssql_missing_schema(fixed) == (fixed, 0)


def test_fix_leaves_public_created_and_unqualified_alone():
    text = "CREATE SCHEMA IF NOT EXISTS app;\nCREATE TABLE app.t (id int);\nCREATE TABLE public.u (id int);\nCREATE TABLE v (id int);\n"
    assert fix_mssql_missing_schema(text) == (text, 0)
