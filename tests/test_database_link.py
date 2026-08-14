from ora2pg_gap_report.detectors.database_link import find_database_link_references


def test_dblink_reference_is_flagged_inside_a_package_body():
    source = """
    create or replace package body remote_sync_pkg as
      procedure pull_remote_orders is
      begin
        insert into local_orders (order_id, customer_id, amount)
        select order_id, customer_id, amount
        from orders@remote_erp_link
        where created_at > sysdate - 1;
        commit;
      end pull_remote_orders;
    end remote_sync_pkg;
    /
    """
    findings = find_database_link_references(source)
    assert len(findings) == 1
    assert findings[0].object_name == "REMOTE_SYNC_PKG.PULL_REMOTE_ORDERS"
    assert findings[0].snippet == "orders@remote_erp_link"
    assert findings[0].severity == "high"


def test_dotted_dblink_names_are_matched_in_full():
    # Oracle dblink names can be dotted (link.domain.com), unlike ordinary
    # identifiers.
    source = """
    create or replace procedure noop as
    begin
      insert into t select * from remote_tab@prod.us.mycorp.com;
    end noop;
    /
    """
    findings = find_database_link_references(source)
    assert len(findings) == 1
    assert findings[0].snippet == "remote_tab@prod.us.mycorp.com"


def test_email_address_in_string_or_comment_is_not_a_false_positive():
    source = """
    create or replace procedure noop as
      v_email varchar2(100) := 'someone@example.com';
    begin
      -- contact us at admin@example.com
      null;
    end noop;
    /
    """
    assert find_database_link_references(source) == []


def test_procedure_without_a_dblink_reference_is_not_flagged():
    source = """
    create or replace package body plain_pkg as
      procedure noop is
      begin
        null;
      end noop;
    end plain_pkg;
    /
    """
    assert find_database_link_references(source) == []


def test_at_sign_inside_a_quoted_identifier_is_not_a_false_positive():
    # An Oracle quoted identifier can legally contain almost any
    # character, including a literal '@' -- '"foo@bar"' is a valid (if
    # unusual) table name, not a database link reference.
    source = '''
    create or replace procedure noop as
    begin
      insert into t select * from "foo@bar";
    end noop;
    /
    '''
    assert find_database_link_references(source) == []
