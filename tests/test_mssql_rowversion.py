from ora2pg_gap_report.detectors.mssql_rowversion import find_mssql_rowversion_columns


def test_the_construct_is_flagged():
    source = (
        "CREATE TABLE versioned (\n"
        "    id int NOT NULL PRIMARY KEY,\n"
        "    rv rowversion NOT NULL\n"
        ");\n"
    )
    findings = find_mssql_rowversion_columns(source)
    assert len(findings) == 1
    assert findings[0].object_name == 'VERSIONED'
    assert findings[0].snippet == 'ROWVERSION'
    assert findings[0].severity == "high"
    assert findings[0].line == 3


def test_an_ordinary_timestamp_column_is_not_flagged():
    # Deliberate: T-SQL's `timestamp` is a deprecated synonym for rowversion,
    # but flagging the bare word would fire on any column merely named that.
    assert find_mssql_rowversion_columns('CREATE TABLE t (id int, created datetime2);\n') == []

def test_a_bare_ctas_is_not_flagged():
    # No column-definition list at all.
    assert find_mssql_rowversion_columns('CREATE TABLE t AS SELECT * FROM other;\n') == []
