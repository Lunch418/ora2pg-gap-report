from ora2pg_gap_report.detectors.mssql_parameterless_procedure import find_mssql_parameterless_procedures


def test_a_parameterless_procedure_is_flagged():
    source = (
        "CREATE PROCEDURE dbo.noparams AS\n"
        "BEGIN\n"
        "    SELECT 1;\n"
        "END;\n"
    )
    findings = find_mssql_parameterless_procedures(source)
    assert len(findings) == 1
    assert findings[0].object_name == "NOPARAMS"
    assert findings[0].severity == "high"
    assert findings[0].line == 1

def test_a_parenthesised_parameter_list_is_not_flagged():
    source = "CREATE PROCEDURE dbo.p (@x int, @y int) AS BEGIN SELECT 1; END;\n"
    assert find_mssql_parameterless_procedures(source) == []


def test_create_or_alter_is_recognised():
    source = "CREATE OR ALTER PROCEDURE dbo.modern AS\nBEGIN\n  SELECT 1;\nEND;\n"
    assert len(find_mssql_parameterless_procedures(source)) == 1


def test_the_construct_inside_a_string_literal_is_not_flagged():
    source = "CREATE PROCEDURE dbo.p @x int AS BEGIN SELECT '@notaparam'; END;\n"
    assert find_mssql_parameterless_procedures(source) == []

def test_a_procedure_with_a_parameter_is_not_flagged():
    # Confirmed by A/B against ora2pg: with a parameter no DECLARE block is
    # emitted at all, so there is nothing to break.
    assert find_mssql_parameterless_procedures('CREATE PROCEDURE dbo.withparams @x int AS BEGIN SELECT 1; END;\n') == []

def test_a_table_is_not_flagged():
    # Not a procedure.
    assert find_mssql_parameterless_procedures('CREATE TABLE t (id int);\n') == []
