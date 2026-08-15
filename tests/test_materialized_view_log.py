from ora2pg_gap_report.detectors.materialized_view_log import find_materialized_view_logs


def test_materialized_view_log_is_flagged():
    source = (
        "create materialized view log on products\n"
        "with rowid, sequence (product_id, name)\n"
        "including new values;\n"
    )
    findings = find_materialized_view_logs(source)
    assert len(findings) == 1
    assert findings[0].object_name == "PRODUCTS"
    assert findings[0].severity == "high"


def test_ordinary_table_is_not_flagged():
    source = "create table products (product_id number);\n"
    assert find_materialized_view_logs(source) == []


def test_materialized_view_itself_is_not_confused_with_the_log():
    # CREATE MATERIALIZED VIEW (no LOG) is a different statement --
    # this detector is only about the LOG variant.
    source = "create materialized view mv_products as select * from products;\n"
    assert find_materialized_view_logs(source) == []
