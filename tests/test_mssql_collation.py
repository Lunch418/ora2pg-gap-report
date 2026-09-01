from ora2pg_gap_report.detectors.mssql_collation import find_mssql_collations


def test_the_construct_is_flagged():
    source = (
        "CREATE TABLE cs1 (\n"
        "    id int NOT NULL PRIMARY KEY,\n"
        "    code varchar(20) COLLATE SQL_Latin1_General_CP1_CS_AS NOT NULL\n"
        ");\n"
    )
    findings = find_mssql_collations(source)
    assert len(findings) == 1
    assert findings[0].object_name == 'CS1'
    assert findings[0].snippet == 'COLLATE SQL_Latin1_General_CP1_CS_AS'
    assert findings[0].severity == "high"
    assert findings[0].line == 3

def test_a_case_insensitive_collation_is_flagged_too():
    # ora2pg's citext mapping happens to fit _CI_ rules, but the clause is
    # still dropped, so the choice should be a conscious one either way.
    source = "CREATE TABLE t (nm varchar(50) COLLATE SQL_Latin1_General_CP1_CI_AS);\n"
    assert len(find_mssql_collations(source)) == 1


def test_a_column_without_a_collation_is_not_flagged():
    # Nothing to lose.
    assert find_mssql_collations('CREATE TABLE t (nm varchar(50) NOT NULL);\n') == []

def test_a_bare_ctas_is_not_flagged():
    # No column-definition list at all.
    assert find_mssql_collations('CREATE TABLE t AS SELECT * FROM other;\n') == []
