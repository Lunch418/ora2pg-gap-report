from ora2pg_gap_report.detectors.mysql_zero_date import find_mysql_zero_dates


def test_a_zero_date_default_is_flagged():
    source = (
        "CREATE TABLE events (\n"
        "  id INT PRIMARY KEY,\n"
        "  happened_on DATE NOT NULL DEFAULT '0000-00-00'\n"
        ");\n"
    )
    findings = find_mysql_zero_dates(source)
    assert len(findings) == 1
    assert findings[0].object_name == "EVENTS"
    assert findings[0].snippet == "'0000-00-00'"
    assert findings[0].severity == "high"
    assert findings[0].line == 3


def test_the_zero_datetime_spelling_is_flagged():
    source = "CREATE TABLE t (d DATETIME DEFAULT '0000-00-00 00:00:00');\n"
    findings = find_mysql_zero_dates(source)
    assert len(findings) == 1
    assert findings[0].snippet == "'0000-00-00 00:00:00'"


def test_an_ordinary_date_default_is_not_flagged():
    assert find_mysql_zero_dates("CREATE TABLE t (d DATE DEFAULT '2024-01-01');\n") == []


def test_a_zero_date_inside_a_comment_is_not_flagged():
    # The comments-only view this detector reads still blanks comments,
    # so a zero date mentioned in a comment is not a finding.
    source = "CREATE TABLE t (\n  d DATE -- was DEFAULT '0000-00-00' once\n);\n"
    assert find_mysql_zero_dates(source) == []


def test_a_bare_ctas_with_no_column_list_is_not_flagged():
    assert find_mysql_zero_dates("CREATE TABLE t AS SELECT * FROM other;\n") == []
