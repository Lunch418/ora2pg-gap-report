from ora2pg_gap_report.detectors.mssql_newid_default import find_mssql_newid_defaults


def test_a_newid_default_is_flagged():
    source = (
        "CREATE TABLE tokens (\n"
        "    id uniqueidentifier NOT NULL DEFAULT NEWID(),\n"
        "    label varchar(50) NULL\n"
        ");\n"
    )
    findings = find_mssql_newid_defaults(source)
    assert len(findings) == 1
    assert findings[0].object_name == "TOKENS"
    assert findings[0].snippet == "NEWID()"
    assert findings[0].line == 2

def test_newsequentialid_is_also_flagged():
    source = "CREATE TABLE t (id uniqueidentifier DEFAULT NEWSEQUENTIALID());\n"
    findings = find_mssql_newid_defaults(source)
    assert [f.snippet for f in findings] == ["NEWSEQUENTIALID()"]


def test_the_construct_inside_a_string_literal_is_not_flagged():
    source = "CREATE TABLE t (nm varchar(50) DEFAULT 'NEWID()');\n"
    assert find_mssql_newid_defaults(source) == []

def test_an_ordinary_default_is_not_flagged():
    # No GUID generation involved.
    assert find_mssql_newid_defaults('CREATE TABLE t (id int DEFAULT 0);\n') == []
