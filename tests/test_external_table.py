from ora2pg_gap_report.detectors.external_table import find_external_tables


def test_organization_external_is_flagged():
    source = (
        "create table ext_orders (order_id number, amount number)\n"
        "organization external (\n"
        "  type oracle_loader\n"
        "  default directory ext_dir\n"
        "  access parameters (records delimited by newline fields terminated by ',')\n"
        "  location ('orders.csv')\n"
        ")\n"
        "reject limit unlimited;\n"
    )
    findings = find_external_tables(source)
    assert len(findings) == 1
    assert findings[0].object_name == "EXT_ORDERS"
    assert findings[0].severity == "high"


def test_ordinary_table_is_not_flagged():
    source = "create table orders (order_id number);\n"
    assert find_external_tables(source) == []


def test_external_table_is_not_misattributed_to_a_later_ordinary_table():
    source = (
        "create table ext_orders (order_id number)\n"
        "organization external (type oracle_loader default directory ext_dir "
        "location ('orders.csv'));\n"
        "create table plain_orders (order_id number);\n"
    )
    findings = find_external_tables(source)
    assert len(findings) == 1
    assert findings[0].object_name == "EXT_ORDERS"
