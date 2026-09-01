from ora2pg_gap_report.detectors.mssql_try_catch import find_mssql_try_catch


def test_the_construct_is_flagged():
    source = (
        "CREATE PROCEDURE dbo.safe @x int AS\n"
        "BEGIN\n"
        "    BEGIN TRY\n"
        "        INSERT INTO t1 (id) VALUES (1);\n"
        "    END TRY\n"
        "    BEGIN CATCH\n"
        "        SELECT ERROR_MESSAGE();\n"
        "    END CATCH\n"
        "END;\n"
    )
    findings = find_mssql_try_catch(source)
    assert len(findings) == 1
    assert findings[0].object_name == 'SAFE'
    assert findings[0].snippet == 'BEGIN TRY'
    assert findings[0].severity == "high"
    assert findings[0].line == 3


def test_a_plain_begin_end_is_not_flagged():
    # An ordinary block, not TRY/CATCH.
    assert find_mssql_try_catch('CREATE PROCEDURE dbo.p AS BEGIN SELECT 1; END;\n') == []

def test_the_keyword_inside_a_string_literal_is_not_flagged():
    # Masked out.
    assert find_mssql_try_catch("CREATE PROCEDURE dbo.p AS BEGIN SELECT 'BEGIN TRY'; END;\n") == []
