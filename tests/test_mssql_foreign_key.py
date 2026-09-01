from ora2pg_gap_report.detectors.mssql_foreign_key import find_mssql_foreign_keys


def test_the_construct_is_flagged():
    source = (
        "CREATE TABLE childx (\n"
        "    id int NOT NULL PRIMARY KEY,\n"
        "    pid int NOT NULL,\n"
        "    CONSTRAINT FK_c FOREIGN KEY (pid) REFERENCES parentx (id) ON DELETE CASCADE\n"
        ");\n"
    )
    findings = find_mssql_foreign_keys(source)
    assert len(findings) == 1
    assert findings[0].object_name == 'CHILDX'
    assert findings[0].snippet == 'FOREIGN KEY'
    assert findings[0].severity == "high"
    assert findings[0].line == 4

def test_the_unnamed_form_is_flagged_too():
    source = "CREATE TABLE c (id int, pid int, FOREIGN KEY (pid) REFERENCES p (id));\n"
    assert len(find_mssql_foreign_keys(source)) == 1


def test_a_table_without_foreign_keys_is_not_flagged():
    # Nothing referential here.
    assert find_mssql_foreign_keys('CREATE TABLE t (id int NOT NULL PRIMARY KEY);\n') == []

def test_a_bare_ctas_is_not_flagged():
    # No column-definition list at all.
    assert find_mssql_foreign_keys('CREATE TABLE t AS SELECT * FROM other;\n') == []
