from ora2pg_gap_report.detectors.mysql_collate import find_mysql_collations


def test_a_column_collation_is_flagged():
    source = (
        "CREATE TABLE col1 (\n"
        "  id INT PRIMARY KEY,\n"
        "  name VARCHAR(50) COLLATE utf8mb4_general_ci NOT NULL\n"
        ");\n"
    )
    findings = find_mysql_collations(source)
    assert len(findings) == 1
    assert findings[0].object_name == "COL1"
    assert findings[0].snippet == "COLLATE utf8mb4_general_ci"
    assert findings[0].severity == "high"
    assert findings[0].line == 3


def test_a_character_set_clause_is_flagged():
    source = "CREATE TABLE t (label VARCHAR(50) CHARACTER SET utf8mb4 NOT NULL);\n"
    findings = find_mysql_collations(source)
    assert [f.snippet for f in findings] == ["CHARACTER SET utf8mb4"]


def test_an_ordinary_column_list_is_not_flagged():
    assert find_mysql_collations("CREATE TABLE t (id INT, name VARCHAR(30));\n") == []


def test_a_table_level_charset_option_is_not_flagged():
    # DEFAULT CHARSET=utf8mb4 sits after the closing paren, outside the
    # column-definition list this detector scopes itself to.
    source = "CREATE TABLE t (id INT) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;\n"
    assert find_mysql_collations(source) == []


def test_a_bare_ctas_with_no_column_list_is_not_flagged():
    assert find_mysql_collations("CREATE TABLE t AS SELECT * FROM other;\n") == []
