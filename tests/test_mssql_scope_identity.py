from ora2pg_gap_report.detectors.mssql_scope_identity import find_mssql_scope_identity


def test_the_construct_is_flagged():
    source = (
        "CREATE PROCEDURE dbo.add_row @x int AS\n"
        "BEGIN\n"
        "    INSERT INTO orders (nm) VALUES ('x');\n"
        "    SELECT SCOPE_IDENTITY();\n"
        "END;\n"
    )
    findings = find_mssql_scope_identity(source)
    assert len(findings) == 1
    assert findings[0].object_name == 'ADD_ROW'
    assert findings[0].snippet == 'SCOPE_IDENTITY'
    assert findings[0].severity == "high"
    assert findings[0].line == 4

def test_the_system_variable_and_ident_current_are_also_flagged():
    assert len(find_mssql_scope_identity("CREATE PROCEDURE dbo.p AS BEGIN SELECT @@IDENTITY; END;\n")) == 1
    assert len(find_mssql_scope_identity("CREATE PROCEDURE dbo.p AS BEGIN SELECT IDENT_CURRENT('t'); END;\n")) == 1


def test_a_procedure_without_it_is_not_flagged():
    # Nothing read back.
    assert find_mssql_scope_identity('CREATE PROCEDURE dbo.p AS BEGIN INSERT INTO t (id) VALUES (1); END;\n') == []

def test_the_call_inside_a_string_literal_is_not_flagged():
    # Masked out.
    assert find_mssql_scope_identity("CREATE PROCEDURE dbo.p AS BEGIN SELECT 'SCOPE_IDENTITY()'; END;\n") == []
