from ora2pg_gap_report.detectors.mysql_set_type import find_mysql_set_columns


def test_a_set_column_is_flagged():
    source = (
        "CREATE TABLE perms (\n"
        "  id INT PRIMARY KEY,\n"
        "  flags SET('read','write','admin') NOT NULL\n"
        ");\n"
    )
    findings = find_mysql_set_columns(source)
    assert len(findings) == 1
    assert findings[0].object_name == "PERMS"
    assert findings[0].snippet == "SET(...)"
    assert findings[0].line == 3


def test_the_severity_is_medium_not_high():
    # Deliberate: unlike ENUM (GAP-068) the schema loads and works, and
    # existing values survive -- only validation of future writes is lost.
    source = "CREATE TABLE t (flags SET('a','b'));\n"
    assert find_mysql_set_columns(source)[0].severity == "medium"


def test_an_ordinary_column_list_is_not_flagged():
    assert find_mysql_set_columns("CREATE TABLE t (id INT, name VARCHAR(30));\n") == []


def test_a_column_named_settings_is_not_flagged():
    assert find_mysql_set_columns("CREATE TABLE t (settings TEXT);\n") == []


def test_a_bare_ctas_with_no_column_list_is_not_flagged():
    assert find_mysql_set_columns("CREATE TABLE t AS SELECT * FROM other;\n") == []
