from ora2pg_gap_report.detectors.local_time_zone import find_local_time_zone_columns


def test_timestamp_with_local_time_zone_column_is_flagged():
    source = (
        "CREATE TABLE durations (\n"
        "    id      NUMBER PRIMARY KEY,\n"
        "    ts_ltz  TIMESTAMP WITH LOCAL TIME ZONE\n"
        ");\n"
    )
    findings = find_local_time_zone_columns(source)
    assert len(findings) == 1
    assert findings[0].object_name == "DURATIONS"
    assert findings[0].snippet == "TIMESTAMP WITH LOCAL TIME ZONE"
    assert findings[0].severity == "high"
    assert findings[0].line == 3


def test_explicit_precision_is_still_flagged():
    source = "create table t (col timestamp(6) with local time zone);\n"
    findings = find_local_time_zone_columns(source)
    assert len(findings) == 1
    assert findings[0].object_name == "T"


def test_plain_timestamp_with_time_zone_is_not_flagged():
    # TIMESTAMP WITH TIME ZONE (no LOCAL) is a different Oracle type that
    # ora2pg maps correctly onto PostgreSQL's timestamptz.
    source = "CREATE TABLE t (a TIMESTAMP WITH TIME ZONE, b TIMESTAMP);\n"
    assert find_local_time_zone_columns(source) == []


def test_a_bare_timestamp_column_is_not_flagged():
    source = "CREATE TABLE t (created_at TIMESTAMP, updated_at DATE);\n"
    assert find_local_time_zone_columns(source) == []


def test_real_oracle_sample_schema_orders_table_is_flagged():
    # Real shape from Oracle's own db-sample-schemas (order_entry/cord_v3.sql):
    # an inline NOT NULL constraint follows the type on the next line.
    source = (
        "CREATE TABLE orders\n"
        "    ( order_id           NUMBER(12)\n"
        "    , order_date         TIMESTAMP WITH LOCAL TIME ZONE\n"
        "CONSTRAINT order_date_nn NOT NULL\n"
        "    , order_mode         VARCHAR2(8)\n"
        "    ) ;\n"
    )
    findings = find_local_time_zone_columns(source)
    assert len(findings) == 1
    assert findings[0].object_name == "ORDERS"
    assert findings[0].line == 3
