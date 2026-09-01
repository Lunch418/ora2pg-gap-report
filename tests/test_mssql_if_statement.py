from ora2pg_gap_report.detectors.mssql_if_statement import find_mssql_if_statements


def test_the_construct_is_flagged():
    source = (
        "CREATE PROCEDURE dbo.p @x int AS\n"
        "BEGIN\n"
        "    IF @x < 0\n"
        "        SELECT 1;\n"
        "END;\n"
    )
    findings = find_mssql_if_statements(source)
    assert len(findings) == 1
    assert findings[0].object_name == 'P'
    assert findings[0].snippet == 'IF'
    assert findings[0].severity == "high"
    assert findings[0].line == 3

def test_the_block_form_is_also_flagged():
    # Both shapes are broken, differently -- the detector does not try to
    # tell them apart, since the fix is the same.
    source = (
        "CREATE PROCEDURE dbo.p @x int AS\n"
        "BEGIN\n"
        "    IF @x < 0\n"
        "    BEGIN\n"
        "        SELECT 1;\n"
        "    END\n"
        "END;\n"
    )
    assert len(find_mssql_if_statements(source)) == 1


def test_iif_does_not_match_if():
    # IIF( must not be read as IF -- there is no word boundary before its IF.
    assert find_mssql_if_statements('CREATE PROCEDURE dbo.p AS BEGIN SELECT IIF(a, 1, 2) FROM t; END;\n') == []

def test_the_keyword_inside_a_string_literal_is_not_flagged():
    # Masked out by the string-aware lexer.
    assert find_mssql_if_statements("CREATE PROCEDURE dbo.p AS BEGIN SELECT 'IF @x < 0'; END;\n") == []

def test_a_procedure_without_a_condition_is_not_flagged():
    # Nothing conditional here.
    assert find_mssql_if_statements('CREATE PROCEDURE dbo.p AS BEGIN SELECT 1; END;\n') == []
