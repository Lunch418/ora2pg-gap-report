from ora2pg_gap_report.detectors.insert_all import find_multitable_inserts


def test_conditional_insert_all_is_flagged():
    source = (
        "create or replace procedure split_orders as\n"
        "begin\n"
        "  insert all\n"
        "    when amount > 1000 then\n"
        "      into big_orders (order_id, amount) values (order_id, amount)\n"
        "    when amount <= 1000 then\n"
        "      into small_orders (order_id, amount) values (order_id, amount)\n"
        "  select order_id, amount from staging_orders;\n"
        "end;\n"
        "/\n"
    )
    findings = find_multitable_inserts(source)
    assert len(findings) == 1
    assert findings[0].object_name == "SPLIT_ORDERS"
    assert findings[0].snippet == "INSERT ALL"
    assert findings[0].severity == "high"


def test_unconditional_insert_first_is_flagged():
    # INSERT FIRST with no WHEN at all is still valid multitable insert
    # syntax -- must still be flagged, the INTO lookahead alone is enough.
    source = (
        "create or replace procedure fan_out as\n"
        "begin\n"
        "  insert first\n"
        "    into audit_log (order_id) values (order_id)\n"
        "    into orders_copy (order_id) values (order_id)\n"
        "  select order_id from staging_orders;\n"
        "end;\n"
        "/\n"
    )
    findings = find_multitable_inserts(source)
    assert len(findings) == 1
    assert findings[0].snippet == "INSERT FIRST"


def test_wide_when_condition_before_into_is_still_flagged():
    # A real WHEN condition can be a sizeable compound boolean expression
    # (wide staging tables, generated ETL conditions) -- the lookahead
    # window must tolerate that instead of silently dropping the finding.
    wide_condition = " and ".join(f"col{i} = {i}" for i in range(60))  # well over 500 chars
    source = (
        "create or replace procedure split_orders as\n"
        "begin\n"
        "  insert all\n"
        f"    when {wide_condition} then\n"
        "      into big_orders (order_id) values (order_id)\n"
        "  select order_id from staging_orders;\n"
        "end;\n"
        "/\n"
    )
    assert len(wide_condition) > 500
    findings = find_multitable_inserts(source)
    assert len(findings) == 1


def test_ordinary_insert_into_is_not_flagged():
    source = "insert into orders (order_id) values (1);\n"
    assert find_multitable_inserts(source) == []


def test_hint_comment_does_not_cause_a_false_positive():
    # A /*+ ALL_ROWS */ optimizer hint right after INSERT must not be
    # mistaken for 'INSERT ALL' -- it's masked out as a comment, so the
    # next real token after INSERT is INTO, not ALL/FIRST.
    source = "insert /*+ ALL_ROWS */ into orders (order_id) values (1);\n"
    assert find_multitable_inserts(source) == []
