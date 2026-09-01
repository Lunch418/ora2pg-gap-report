from ora2pg_gap_report.detectors.mssql_identity_column import find_mssql_identity_columns


def test_an_identity_column_is_flagged():
    source = (
        "CREATE TABLE invoices (\n"
        "    id int IDENTITY(1,1) NOT NULL PRIMARY KEY,\n"
        "    amount decimal(10,2) NOT NULL\n"
        ");\n"
    )
    findings = find_mssql_identity_columns(source)
    assert len(findings) == 1
    assert findings[0].object_name == "INVOICES"
    assert findings[0].snippet == "IDENTITY"
    assert findings[0].severity == "high"
    assert findings[0].line == 2

def test_the_bare_identity_spelling_is_flagged():
    assert len(find_mssql_identity_columns("CREATE TABLE t (id int IDENTITY NOT NULL);\n")) == 1


def test_the_construct_inside_a_string_literal_is_not_flagged():
    source = "CREATE TABLE t (nm varchar(50) DEFAULT 'IDENTITY(1,1)');\n"
    assert find_mssql_identity_columns(source) == []

def test_a_plain_integer_column_is_not_flagged():
    # Nothing auto-incrementing here.
    assert find_mssql_identity_columns('CREATE TABLE t (id int NOT NULL);\n') == []

def test_a_bare_ctas_is_not_flagged():
    # No column-definition list at all.
    assert find_mssql_identity_columns('CREATE TABLE t AS SELECT * FROM other;\n') == []
