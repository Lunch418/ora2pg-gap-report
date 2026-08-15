from ora2pg_gap_report.detectors.global_temp_table import find_global_temp_tables_without_delete_rows


def test_explicit_delete_rows_is_flagged():
    source = "create global temporary table staging_orders (order_id number) on commit delete rows;\n"
    findings = find_global_temp_tables_without_delete_rows(source)
    assert len(findings) == 1
    assert findings[0].object_name == "STAGING_ORDERS"
    assert findings[0].severity == "high"


def test_omitted_on_commit_clause_is_also_flagged():
    # Oracle's default when ON COMMIT is omitted entirely is DELETE ROWS
    # -- just as dangerous as the explicit form once ora2pg drops it.
    source = "create global temporary table staging_orders2 (order_id number);\n"
    findings = find_global_temp_tables_without_delete_rows(source)
    assert len(findings) == 1
    assert findings[0].object_name == "STAGING_ORDERS2"


def test_explicit_preserve_rows_is_not_flagged():
    # Confirmed against a real PostgreSQL 16 server: this case matches
    # PostgreSQL's own default and converts correctly.
    source = "create global temporary table staging_orders3 (order_id number) on commit preserve rows;\n"
    assert find_global_temp_tables_without_delete_rows(source) == []


def test_ordinary_table_is_not_flagged():
    source = "create table orders (order_id number);\n"
    assert find_global_temp_tables_without_delete_rows(source) == []


def test_unterminated_statement_does_not_bleed_into_an_earlier_table():
    # DBMS_METADATA.GET_DDL's default output (this project's own
    # documented Oracle export mechanism) has no trailing ';' -- scoping
    # "this table's own text" to just "next ';' or end of file" used to
    # let a later table's own PRESERVE ROWS clause bleed all the way back
    # to an earlier, unrelated, unterminated table and wrongly suppress
    # its finding.
    source = (
        "create global temporary table staging_a (id number)\n"
        "create global temporary table staging_b (id number) on commit preserve rows\n"
    )
    findings = find_global_temp_tables_without_delete_rows(source)
    assert len(findings) == 1
    assert findings[0].object_name == "STAGING_A"
