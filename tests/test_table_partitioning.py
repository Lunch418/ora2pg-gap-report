from ora2pg_gap_report.detectors.table_partitioning import find_dropped_table_partitioning


def test_range_partitioning_is_flagged():
    source = (
        "create table sales (sale_date date, amount number)\n"
        "partition by range (sale_date) (\n"
        "  partition p1 values less than (date '2020-01-01'),\n"
        "  partition p2 values less than (maxvalue)\n"
        ");\n"
    )
    findings = find_dropped_table_partitioning(source)
    assert len(findings) == 1
    assert findings[0].object_name == "SALES"
    assert findings[0].severity == "high"
    assert "RANGE" in findings[0].snippet


def test_list_and_hash_partitioning_are_also_flagged():
    list_source = "create table regions (region_code varchar2(2)) partition by list (region_code) (partition p1 values ('EU'));\n"
    hash_source = "create table customers (customer_id number) partition by hash (customer_id) partitions 4;\n"
    assert len(find_dropped_table_partitioning(list_source)) == 1
    assert len(find_dropped_table_partitioning(hash_source)) == 1


def test_partitioned_outer_join_is_not_flagged():
    # Collision risk: "PARTITION BY" also appears in Oracle's partitioned
    # outer join syntax, which has nothing to do with table partitioning
    # and must not be flagged -- there's no RANGE/LIST/HASH keyword there.
    source = (
        "select * from sales s partition by (s.region) "
        "right outer join regions r on s.region = r.region_code;\n"
    )
    assert find_dropped_table_partitioning(source) == []


def test_window_function_partition_by_is_not_flagged():
    source = "select sum(amount) over (partition by region order by sale_date) from sales;\n"
    assert find_dropped_table_partitioning(source) == []


def test_ordinary_table_is_not_flagged():
    source = "create table orders (order_id number);\n"
    assert find_dropped_table_partitioning(source) == []


def test_partitioned_index_is_not_misattributed_to_an_unrelated_table():
    # A partitioned *index* is valid, distinct Oracle syntax
    # ('CREATE INDEX ... GLOBAL PARTITION BY RANGE (col) (...)') and is not
    # what this detector is about. It must not be matched at all, and
    # certainly not misattributed to an unrelated table that happens to
    # appear earlier in the file.
    source = (
        "create table small_lookup (id number);\n"
        "create index idx1 on some_table (col) global partition by range (col) "
        "(partition p1 values less than (100), partition p2 values less than (maxvalue));\n"
    )
    assert find_dropped_table_partitioning(source) == []


def test_reference_partitioning_is_flagged():
    source = (
        "create table order_items (order_id number, "
        "constraint fk_order foreign key (order_id) references orders (order_id))\n"
        "partition by reference (fk_order);\n"
    )
    findings = find_dropped_table_partitioning(source)
    assert len(findings) == 1
    assert findings[0].object_name == "ORDER_ITEMS"
    assert "REFERENCE" in findings[0].snippet


def test_system_partitioning_is_flagged():
    source = "create table logs (msg varchar2(200)) partition by system partitions 4;\n"
    findings = find_dropped_table_partitioning(source)
    assert len(findings) == 1
    assert findings[0].object_name == "LOGS"
    assert "SYSTEM" in findings[0].snippet


def test_real_oracle_sample_schema_sales_table_is_flagged():
    # The exact real-world shape this gap was originally found on: the
    # SALES fact table from Oracle's own official sample schemas
    # (oracle-samples/db-sample-schemas, sales_history/sh_create.sql) --
    # a genuine, widely-used example of range partitioning by date, not a
    # synthetic construction. Kept as a permanent regression check tying
    # this detector to that real source, per docs/research/AUDIT.md.
    source = """
    CREATE TABLE sales
    (
       prod_id         NUMBER(6)      NOT NULL,
       cust_id         NUMBER         NOT NULL,
       time_id         DATE           NOT NULL,
       channel_id      NUMBER(1)      NOT NULL,
       promo_id        NUMBER(6)      NOT NULL,
       quantity_sold   NUMBER(3)      NOT NULL,
       amount_sold     NUMBER(10,2)   NOT NULL
    )
     PARTITION BY RANGE (time_id)
     (
        PARTITION SALES_2018 VALUES LESS THAN
           (TO_DATE('2019-01-01','YYYY-MM-DD','NLS_DATE_LANGUAGE = American')),
        PARTITION SALES_H1_2019 VALUES LESS THAN
           (TO_DATE('2019-07-01','YYYY-MM-DD','NLS_DATE_LANGUAGE = American'))
     );
    """
    findings = find_dropped_table_partitioning(source)
    assert len(findings) == 1
    assert findings[0].object_name == "SALES"
    assert "RANGE" in findings[0].snippet


def test_unterminated_statement_does_not_bleed_into_an_earlier_table():
    # DBMS_METADATA.GET_DDL's default output (this project's own
    # documented Oracle export mechanism) has no trailing ';' --
    # scoping "this table's own text" to just "next ';' or end of file"
    # used to let a later table's PARTITION BY bleed all the way back to
    # an earlier, unrelated, unterminated table.
    source = (
        "create table small_lookup (id number)\n"
        "create table sales (id number, dt date)\n"
        "partition by range (dt) (partition p1 values less than (100))\n"
    )
    findings = find_dropped_table_partitioning(source)
    assert len(findings) == 1
    assert findings[0].object_name == "SALES"
