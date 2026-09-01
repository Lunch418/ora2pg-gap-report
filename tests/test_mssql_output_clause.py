from ora2pg_gap_report.detectors.mssql_output_clause import find_mssql_output_clause


def test_the_construct_is_flagged():
    source = (
        "CREATE PROCEDURE dbo.with_out @x int AS\n"
        "BEGIN\n"
        "    INSERT INTO orders (nm) OUTPUT INSERTED.id VALUES ('x');\n"
        "END;\n"
    )
    findings = find_mssql_output_clause(source)
    assert len(findings) == 1
    assert findings[0].object_name == 'WITH_OUT'
    assert findings[0].snippet == 'OUTPUT INSERTED.'
    assert findings[0].severity == "high"
    assert findings[0].line == 3

def test_the_deleted_form_is_also_flagged():
    source = "CREATE PROCEDURE dbo.p AS BEGIN DELETE FROM t OUTPUT DELETED.id; END;\n"
    assert len(find_mssql_output_clause(source)) == 1


def test_a_returning_clause_is_not_flagged():
    # Already the PostgreSQL spelling.
    assert find_mssql_output_clause("CREATE PROCEDURE dbo.p AS BEGIN INSERT INTO t (nm) VALUES ('x') RETURNING id; END;\n") == []

def test_an_output_parameter_is_not_flagged():
    # OUTPUT as a parameter direction is a different construct entirely -- the
    # INSERTED./DELETED. prefix is what makes it the clause.
    assert find_mssql_output_clause('CREATE PROCEDURE dbo.p @total int OUTPUT AS BEGIN SELECT 1; END;\n') == []

def test_the_clause_inside_a_string_literal_is_not_flagged():
    # Masked out.
    assert find_mssql_output_clause("CREATE PROCEDURE dbo.p AS BEGIN SELECT 'OUTPUT INSERTED.id'; END;\n") == []
