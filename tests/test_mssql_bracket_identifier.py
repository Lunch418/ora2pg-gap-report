from ora2pg_gap_report.detectors.mssql_bracket_identifier import find_mssql_bracket_identifiers


def test_a_bracket_quoted_create_table_is_flagged():
    # Exactly the shape SSMS emits by default.
    source = (
        "CREATE TABLE [dbo].[Orders](\n"
        "    [Id] [int] IDENTITY(1,1) NOT NULL,\n"
        "    [Total] [money] NULL\n"
        ");\n"
    )
    findings = find_mssql_bracket_identifiers(source)
    assert len(findings) == 1
    assert findings[0].object_name == "ORDERS"
    assert findings[0].severity == "high"
    assert findings[0].line == 1

def test_a_bracketed_procedure_name_with_a_space_is_flagged():
    source = "CREATE PROCEDURE [dbo].[Do Work] @x int AS\nBEGIN\n  SELECT 1;\nEND;\n"
    findings = find_mssql_bracket_identifiers(source)
    assert len(findings) == 1
    assert findings[0].object_name == "DO WORK"


def test_one_finding_per_object_not_per_bracket():
    # A 200-bracket script must not produce 200 findings -- the actionable
    # unit is "this object will not convert".
    source = (
        "CREATE TABLE [dbo].[A]([x] [int], [y] [int], [z] [int]);\n"
        "CREATE TABLE [dbo].[B]([x] [int], [y] [int]);\n"
    )
    assert len(find_mssql_bracket_identifiers(source)) == 2


def test_the_construct_inside_a_string_literal_is_not_flagged():
    source = "CREATE PROCEDURE dbo.p AS BEGIN SELECT '[dbo].[Orders]'; END;\n"
    assert find_mssql_bracket_identifiers(source) == []

def test_an_unbracketed_create_table_is_not_flagged():
    # The same table without brackets converts correctly.
    assert find_mssql_bracket_identifiers('CREATE TABLE dbo.Orders (Id int NOT NULL);\n') == []
