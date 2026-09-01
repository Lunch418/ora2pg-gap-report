from ora2pg_gap_report.detectors.mssql_raiserror import find_mssql_raiserror


def test_the_construct_is_flagged():
    source = (
        "CREATE PROCEDURE dbo.chk @amt int AS\n"
        "BEGIN\n"
        "    RAISERROR ('amount must be positive', 16, 1);\n"
        "END;\n"
    )
    findings = find_mssql_raiserror(source)
    assert len(findings) == 1
    assert findings[0].object_name == 'CHK'
    assert findings[0].snippet == 'RAISERROR'
    assert findings[0].severity == "high"
    assert findings[0].line == 3

def test_throw_is_also_flagged():
    source = "CREATE PROCEDURE dbo.p AS BEGIN THROW 50001, 'bad', 1; END;\n"
    findings = find_mssql_raiserror(source)
    assert [f.snippet for f in findings] == ["THROW"]


def test_a_procedure_without_it_is_not_flagged():
    # No error raised at all.
    assert find_mssql_raiserror('CREATE PROCEDURE dbo.p AS BEGIN SELECT 1; END;\n') == []

def test_the_keyword_inside_a_string_literal_is_not_flagged():
    # Masked out.
    assert find_mssql_raiserror("CREATE PROCEDURE dbo.p AS BEGIN SELECT 'RAISERROR here'; END;\n") == []

def test_a_similarly_named_column_is_not_flagged():
    # THROW must match as a whole word only.
    assert find_mssql_raiserror('CREATE TABLE t (throw_count int);\n') == []
