from ora2pg_gap_report.detectors.mysql_spatial_index import find_mysql_spatial_indexes


def test_a_spatial_key_is_flagged():
    source = (
        "CREATE TABLE places (\n"
        "  id INT PRIMARY KEY,\n"
        "  loc POINT NOT NULL,\n"
        "  SPATIAL KEY sp_loc (loc)\n"
        ");\n"
    )
    findings = find_mysql_spatial_indexes(source)
    assert len(findings) == 1
    assert findings[0].object_name == "PLACES"
    assert findings[0].snippet == "SPATIAL KEY"
    assert findings[0].severity == "high"
    assert findings[0].line == 4


def test_the_spatial_index_spelling_is_also_flagged():
    source = "CREATE TABLE t (loc POINT, SPATIAL INDEX sp (loc));\n"
    findings = find_mysql_spatial_indexes(source)
    assert len(findings) == 1
    assert findings[0].snippet == "SPATIAL INDEX"


def test_a_plain_key_is_left_to_its_own_gap():
    assert find_mysql_spatial_indexes("CREATE TABLE t (a INT, KEY k (a));\n") == []


def test_an_ordinary_column_list_is_not_flagged():
    assert find_mysql_spatial_indexes("CREATE TABLE t (id INT, name VARCHAR(30));\n") == []


def test_a_column_named_spatial_something_is_not_flagged():
    assert find_mysql_spatial_indexes("CREATE TABLE t (spatial_ref INT);\n") == []
