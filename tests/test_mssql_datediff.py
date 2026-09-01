from ora2pg_gap_report.detectors.mssql_datediff import find_mssql_datediff


def test_the_construct_is_flagged():
    source = (
        "CREATE PROCEDURE dbo.dates @x int AS\n"
        "BEGIN\n"
        "    SELECT DATEDIFF(day, created, GETDATE()) FROM orders;\n"
        "END;\n"
    )
    findings = find_mssql_datediff(source)
    assert len(findings) == 1
    assert findings[0].object_name == 'DATES'
    assert findings[0].snippet == 'DATEDIFF(...)'
    assert findings[0].severity == "high"
    assert findings[0].line == 3


def test_dateadd_is_not_flagged():
    # DATEADD is converted correctly by ora2pg and is deliberately not flagged.
    assert find_mssql_datediff('CREATE PROCEDURE dbo.p AS BEGIN SELECT DATEADD(day, 7, created) FROM t; END;\n') == []

def test_datepart_is_not_flagged():
    # Also converted correctly, into date_part().
    assert find_mssql_datediff('CREATE PROCEDURE dbo.p AS BEGIN SELECT DATEPART(year, created) FROM t; END;\n') == []

def test_the_call_inside_a_string_literal_is_not_flagged():
    # Masked out.
    assert find_mssql_datediff("CREATE PROCEDURE dbo.p AS BEGIN SELECT 'DATEDIFF(day, a, b)'; END;\n") == []
