from ora2pg_gap_report.detectors.anydata_type import find_anydata_columns


def test_a_qualified_anydata_column_is_flagged():
    source = (
        "CREATE TABLE settings (\n"
        "    id  NUMBER PRIMARY KEY,\n"
        "    val SYS.ANYDATA\n"
        ");\n"
    )
    findings = find_anydata_columns(source)
    assert len(findings) == 1
    assert findings[0].object_name == "SETTINGS"
    assert findings[0].snippet == "ANYDATA"
    assert findings[0].severity == "high"
    assert findings[0].line == 3


def test_the_unqualified_spelling_is_flagged():
    assert len(find_anydata_columns("CREATE TABLE t (val ANYDATA);\n")) == 1


def test_anydataset_and_anytype_are_flagged():
    source = "CREATE TABLE t (a SYS.ANYDATASET, b ANYTYPE);\n"
    findings = find_anydata_columns(source)
    assert [f.snippet for f in findings] == ["ANYDATASET", "ANYTYPE"]


def test_an_ordinary_column_list_is_not_flagged():
    assert find_anydata_columns("CREATE TABLE t (id NUMBER, name VARCHAR2(30));\n") == []


def test_a_similarly_named_column_is_not_flagged():
    # `anydata_id` must not match -- the pattern is word-bounded.
    assert find_anydata_columns("CREATE TABLE t (anydata_id NUMBER);\n") == []
