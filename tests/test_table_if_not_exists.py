from ora2pg_gap_report.detectors.table_if_not_exists import find_table_if_not_exists


def test_an_oracle_create_table_if_not_exists_is_flagged():
    source = "CREATE TABLE IF NOT EXISTS customers (\n  id NUMBER PRIMARY KEY,\n  name VARCHAR2(50)\n);\n"
    findings = find_table_if_not_exists(source)
    assert [(f.object_name, f.line, f.severity) for f in findings] == [("CUSTOMERS", 1, "high")]


def test_a_schema_qualified_quoted_name_is_read():
    assert [f.object_name for f in find_table_if_not_exists('CREATE TABLE IF NOT EXISTS "HR"."T" (id NUMBER);')] == ["T"]


def test_a_plain_create_table_is_not_flagged():
    assert find_table_if_not_exists("CREATE TABLE customers (id NUMBER);\n") == []


def test_if_not_exists_in_a_comment_or_string_is_not_flagged():
    source = "-- CREATE TABLE IF NOT EXISTS t (id NUMBER);\nSELECT 'CREATE TABLE IF NOT EXISTS t' FROM dual;\n"
    assert find_table_if_not_exists(source) == []
