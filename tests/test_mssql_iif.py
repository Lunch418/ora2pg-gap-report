from ora2pg_gap_report.detectors.mssql_iif import find_mssql_iif


def test_the_construct_is_flagged():
    source = (
        "CREATE PROCEDURE dbo.use_iif @x int AS\n"
        "BEGIN\n"
        "    SELECT IIF(amount > 0, 'pos', 'neg') FROM orders;\n"
        "END;\n"
    )
    findings = find_mssql_iif(source)
    assert len(findings) == 1
    assert findings[0].object_name == 'USE_IIF'
    assert findings[0].snippet == 'IIF(...)'
    assert findings[0].severity == "high"
    assert findings[0].line == 3


def test_a_case_expression_is_not_flagged():
    # Already the portable spelling.
    assert find_mssql_iif('CREATE PROCEDURE dbo.p AS BEGIN SELECT CASE WHEN a > 0 THEN 1 ELSE 2 END FROM t; END;\n') == []

def test_a_plain_if_is_not_flagged():
    # The IF statement is GAP-092's business, not this one's.
    assert find_mssql_iif('CREATE PROCEDURE dbo.p @x int AS BEGIN IF @x < 0 SELECT 1; END;\n') == []

def test_the_call_inside_a_string_literal_is_not_flagged():
    # Masked out.
    assert find_mssql_iif("CREATE PROCEDURE dbo.p AS BEGIN SELECT 'IIF(a,1,2)'; END;\n") == []
