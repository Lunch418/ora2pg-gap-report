from ora2pg_gap_report.detectors.mssql_charindex import find_mssql_charindex


def test_the_construct_is_flagged():
    source = (
        "CREATE PROCEDURE dbo.ci @nm varchar(50) AS\n"
        "BEGIN\n"
        "    SELECT CHARINDEX('abc', @nm);\n"
        "END;\n"
    )
    findings = find_mssql_charindex(source)
    assert len(findings) == 1
    assert findings[0].object_name == 'CI'
    assert findings[0].snippet == 'CHARINDEX(...)'
    assert findings[0].severity == "high"
    assert findings[0].line == 3


def test_an_already_converted_position_call_is_not_flagged():
    # This is the target spelling, not the source one.
    assert find_mssql_charindex("CREATE PROCEDURE dbo.p AS BEGIN SELECT position('a' in nm) FROM t; END;\n") == []

def test_the_call_inside_a_string_literal_is_not_flagged():
    # Masked out.
    assert find_mssql_charindex("CREATE PROCEDURE dbo.p AS BEGIN SELECT 'CHARINDEX(a, b)'; END;\n") == []

def test_a_similarly_named_column_is_not_flagged():
    # Must match as a whole word plus a paren.
    assert find_mssql_charindex('CREATE TABLE t (charindex_value int);\n') == []
