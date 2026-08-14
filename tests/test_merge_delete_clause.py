from ora2pg_gap_report.detectors.merge_delete_clause import find_merge_delete_clauses


def test_merge_with_delete_where_is_flagged_inside_a_package_body():
    source = """
    create or replace package body merge_test_pkg as
      procedure sync_customers is
      begin
        MERGE INTO customers c
        USING staging_customers s
        ON (c.customer_id = s.customer_id)
        WHEN MATCHED THEN
          UPDATE SET c.name = s.name
          WHERE s.name IS NOT NULL
          DELETE WHERE s.is_deleted = 1
        WHEN NOT MATCHED THEN
          INSERT (customer_id, name)
          VALUES (s.customer_id, s.name);
      end sync_customers;
    end merge_test_pkg;
    /
    """
    findings = find_merge_delete_clauses(source)
    assert len(findings) == 1
    assert findings[0].object_name == "MERGE_TEST_PKG.SYNC_CUSTOMERS"
    assert findings[0].snippet.upper() == "DELETE WHERE"
    assert findings[0].severity == "high"


def test_plain_merge_without_delete_where_is_not_flagged():
    # Confirmed against a real PostgreSQL 16 server (see
    # docs/research/gap-002-merge-delete-clause.md): plain MERGE with only
    # UPDATE/INSERT branches converts and runs correctly. Flagging it would
    # be exactly the keyword-driven false positive this project avoids.
    source = """
    create or replace package body merge_plain_pkg as
      procedure sync_customers is
      begin
        MERGE INTO customers c
        USING staging_customers s
        ON (c.customer_id = s.customer_id)
        WHEN MATCHED THEN
          UPDATE SET c.name = s.name
        WHEN NOT MATCHED THEN
          INSERT (customer_id, name)
          VALUES (s.customer_id, s.name);
      end sync_customers;
    end merge_plain_pkg;
    /
    """
    assert find_merge_delete_clauses(source) == []


def test_merge_delete_where_is_flagged_in_a_standalone_procedure():
    source = """
    create or replace procedure standalone_sync as
    begin
      MERGE INTO t USING s ON (t.id = s.id)
      WHEN MATCHED THEN UPDATE SET t.x = s.x DELETE WHERE s.flag = 1
      WHEN NOT MATCHED THEN INSERT (id, x) VALUES (s.id, s.x);
    end standalone_sync;
    /
    """
    findings = find_merge_delete_clauses(source)
    assert len(findings) == 1
    assert findings[0].object_name == "STANDALONE_SYNC"


def test_ordinary_delete_statement_is_not_a_false_positive():
    # Oracle allows DELETE without FROM ('DELETE table WHERE ...'), but an
    # ordinary standalone DELETE always has a table reference between
    # DELETE and WHERE — only MERGE's compound clause has "DELETE WHERE"
    # with nothing in between.
    source = """
    create or replace procedure ordinary_delete as
    begin
      DELETE orders WHERE order_id = 5;
      DELETE FROM orders WHERE order_id = 6;
    end ordinary_delete;
    /
    """
    assert find_merge_delete_clauses(source) == []


def test_string_and_comment_content_does_not_trigger_a_false_positive():
    source = """
    create or replace procedure noop as
      v_text varchar2(200) := 'this is a MERGE INTO x DELETE WHERE y example';
    begin
      -- MERGE INTO t USING s ON (1=1) WHEN MATCHED THEN UPDATE SET x=1 DELETE WHERE y=1
      null;
    end noop;
    /
    """
    assert find_merge_delete_clauses(source) == []
