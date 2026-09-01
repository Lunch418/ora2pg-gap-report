from ora2pg_gap_report.detectors.mssql_top_clause import find_mssql_top_clause


def test_the_construct_is_flagged():
    source = (
        "CREATE PROCEDURE dbo.recent @n int AS\n"
        "BEGIN\n"
        "    SELECT TOP 10 id FROM orders ORDER BY id DESC;\n"
        "END;\n"
    )
    findings = find_mssql_top_clause(source)
    assert len(findings) == 1
    assert findings[0].object_name == 'RECENT'
    assert findings[0].snippet == 'TOP n'
    assert findings[0].severity == "high"
    assert findings[0].line == 3

def test_the_parenthesised_and_variable_forms_are_flagged():
    assert len(find_mssql_top_clause("CREATE PROCEDURE dbo.p AS BEGIN SELECT TOP (5) id FROM t; END;\n")) == 1
    assert len(find_mssql_top_clause("CREATE PROCEDURE dbo.p @n int AS BEGIN SELECT TOP @n id FROM t; END;\n")) == 1


def test_a_limit_is_not_flagged():
    # Already the PostgreSQL spelling.
    assert find_mssql_top_clause('CREATE PROCEDURE dbo.p AS BEGIN SELECT id FROM t LIMIT 10; END;\n') == []

def test_a_column_named_topic_is_not_flagged():
    # TOP must match as a whole word.
    assert find_mssql_top_clause('CREATE TABLE t (topic varchar(50));\n') == []

def test_the_keyword_inside_a_string_literal_is_not_flagged():
    # Masked out.
    assert find_mssql_top_clause("CREATE PROCEDURE dbo.p AS BEGIN SELECT 'TOP 10'; END;\n") == []
