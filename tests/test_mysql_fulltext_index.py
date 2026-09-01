from ora2pg_gap_report.detectors.mysql_fulltext_index import find_mysql_fulltext_indexes


def test_a_fulltext_key_is_flagged():
    source = (
        "CREATE TABLE articles (\n"
        "  id INT PRIMARY KEY,\n"
        "  title VARCHAR(200),\n"
        "  body TEXT,\n"
        "  FULLTEXT KEY ft_body (title, body)\n"
        ");\n"
    )
    findings = find_mysql_fulltext_indexes(source)
    assert len(findings) == 1
    assert findings[0].object_name == "ARTICLES"
    assert findings[0].snippet == "FULLTEXT KEY"
    assert findings[0].severity == "high"
    assert findings[0].line == 5


def test_a_fulltext_index_spelling_is_also_flagged():
    source = "CREATE TABLE t (body TEXT, FULLTEXT INDEX ft (body));\n"
    findings = find_mysql_fulltext_indexes(source)
    assert len(findings) == 1
    assert findings[0].snippet == "FULLTEXT INDEX"


def test_an_ordinary_column_list_is_not_flagged():
    assert find_mysql_fulltext_indexes("CREATE TABLE t (id INT, name VARCHAR(30));\n") == []


def test_a_column_named_fulltext_is_not_flagged():
    assert find_mysql_fulltext_indexes("CREATE TABLE t (fulltext_search VARCHAR(30));\n") == []


def test_a_bare_ctas_with_no_column_list_is_not_flagged():
    assert find_mysql_fulltext_indexes("CREATE TABLE t AS SELECT * FROM other;\n") == []


def test_the_phrase_inside_a_string_literal_is_not_flagged():
    source = "CREATE TABLE t (note VARCHAR(50) DEFAULT 'FULLTEXT KEY (x)');\n"
    assert find_mysql_fulltext_indexes(source) == []
