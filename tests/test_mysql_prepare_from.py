from ora2pg_gap_report.detectors.mysql_prepare_from import find_mysql_prepare_from


def test_prepare_from_is_flagged():
    source = (
        "CREATE PROCEDURE p25()\n"
        "BEGIN\n"
        "  SET @s = 'SELECT COUNT(*) FROM t25';\n"
        "  PREPARE stmt FROM @s;\n"
        "END;\n"
    )
    findings = find_mysql_prepare_from(source)
    assert len(findings) == 1
    assert findings[0].object_name == "P25"
    assert findings[0].snippet == "PREPARE ... FROM"
    assert findings[0].severity == "high"
    assert findings[0].line == 4


def test_the_postgresql_prepare_as_spelling_is_not_flagged():
    # PREPARE name AS query is valid PostgreSQL and must not be flagged --
    # ora2pg output can legitimately contain it.
    source = "CREATE PROCEDURE p() BEGIN PREPARE s AS SELECT 1; END;\n"
    assert find_mysql_prepare_from(source) == []


def test_a_procedure_without_prepare_is_not_flagged():
    assert find_mysql_prepare_from("CREATE PROCEDURE p() BEGIN SELECT 1; END;\n") == []


def test_the_phrase_inside_a_string_literal_is_not_flagged():
    source = "CREATE PROCEDURE p() BEGIN SELECT 'PREPARE stmt FROM x'; END;\n"
    assert find_mysql_prepare_from(source) == []
