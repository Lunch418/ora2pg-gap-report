from ora2pg_gap_report.detectors.mssql_computed_column import find_mssql_computed_columns


def test_the_construct_is_flagged():
    source = (
        "CREATE TABLE items3 (\n"
        "    id int NOT NULL PRIMARY KEY,\n"
        "    price decimal(10,2) NOT NULL,\n"
        "    qty int NOT NULL,\n"
        "    total AS (price * qty) PERSISTED\n"
        ");\n"
    )
    findings = find_mssql_computed_columns(source)
    assert len(findings) == 1
    assert findings[0].object_name == 'ITEMS3'
    assert findings[0].snippet == 'AS (...)'
    assert findings[0].severity == "high"
    assert findings[0].line == 5

def test_the_non_persisted_form_is_flagged_too():
    source = "CREATE TABLE t (a int, b int, c AS (a + b));\n"
    assert len(find_mssql_computed_columns(source)) == 1


def test_an_ordinary_column_list_is_not_flagged():
    # No computed column here.
    assert find_mssql_computed_columns('CREATE TABLE t (id int, nm varchar(50));\n') == []

def test_a_bare_ctas_is_not_flagged():
    # CREATE TABLE ... AS SELECT has no column-definition list, so the AS that
    # introduces the query is never mistaken for a computed column.
    assert find_mssql_computed_columns('CREATE TABLE t AS SELECT * FROM other;\n') == []
