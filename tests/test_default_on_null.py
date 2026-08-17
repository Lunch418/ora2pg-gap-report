from ora2pg_gap_report.detectors.default_on_null import find_default_on_null_usage


def test_default_on_null_is_flagged():
    source = "create table orders (order_id number, status varchar2(20) default on null 'PENDING');\n"
    findings = find_default_on_null_usage(source)
    assert len(findings) == 1
    assert findings[0].object_name == "ORDERS"
    assert findings[0].severity == "high"
    assert "ON NULL" in findings[0].snippet.upper()


def test_plain_default_without_on_null_is_not_flagged():
    source = "create table orders (order_id number, status varchar2(20) default 'PENDING');\n"
    assert find_default_on_null_usage(source) == []


def test_no_default_at_all_is_not_flagged():
    source = "create table orders (order_id number, status varchar2(20));\n"
    assert find_default_on_null_usage(source) == []


def test_two_columns_only_the_one_with_on_null_is_flagged():
    source = (
        "create table orders (\n"
        "  status varchar2(20) default 'PENDING',\n"
        "  qty number default on null 0\n"
        ");\n"
    )
    findings = find_default_on_null_usage(source)
    assert len(findings) == 1


def test_default_on_null_is_not_misattributed_to_a_later_unrelated_table():
    source = (
        "create table orders (id number, status varchar2(20) default on null 'PENDING');\n"
        "create table other_table (id number);\n"
    )
    findings = find_default_on_null_usage(source)
    assert len(findings) == 1
    assert findings[0].object_name == "ORDERS"


def test_unterminated_statement_does_not_bleed_into_an_earlier_table():
    source = (
        "create table small_lookup (id number)\n"
        "create table orders (id number, status varchar2(20) default on null 'PENDING')\n"
    )
    findings = find_default_on_null_usage(source)
    assert len(findings) == 1
    assert findings[0].object_name == "ORDERS"


def test_reported_line_is_the_default_clause_line():
    source = (
        "create table orders (\n"
        "  order_id number,\n"
        "  status varchar2(20) default on null 'PENDING'\n"
        ");\n"
    )
    findings = find_default_on_null_usage(source)
    assert len(findings) == 1
    assert findings[0].line == 3
