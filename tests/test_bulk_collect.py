from ora2pg_gap_report.detectors.bulk_collect import find_bulk_collect_usage


def test_type_declaration_bulk_collect_and_forall_are_all_flagged():
    source = """
    create or replace package body bulk_test_pkg as
      procedure archive_old_orders is
        type t_id_tab is table of orders.order_id%type;
        v_ids t_id_tab;
      begin
        select order_id
        bulk collect into v_ids
        from orders
        where status = 'CLOSED';

        forall i in 1 .. v_ids.count
          delete from orders where order_id = v_ids(i);

        commit;
      end archive_old_orders;
    end bulk_test_pkg;
    /
    """
    findings = find_bulk_collect_usage(source)
    assert len(findings) == 3
    assert {f.object_name for f in findings} == {"BULK_TEST_PKG.ARCHIVE_OLD_ORDERS"}
    assert {f.severity for f in findings} == {"high"}
    snippets = {f.snippet.lower() for f in findings}
    assert snippets == {"type t_id_tab is table of", "bulk collect into", "forall"}


def test_bulk_collect_and_forall_flagged_in_a_standalone_procedure():
    source = """
    create or replace procedure standalone_archive as
      type t_id_tab is table of number;
      v_ids t_id_tab;
    begin
      select id bulk collect into v_ids from t;
      forall i in 1 .. v_ids.count
        delete from t where id = v_ids(i);
    end standalone_archive;
    /
    """
    findings = find_bulk_collect_usage(source)
    assert {f.object_name for f in findings} == {"STANDALONE_ARCHIVE"}
    assert len(findings) == 3


def test_local_collection_type_in_a_package_spec_is_attributed_not_unknown():
    # Found by scanning a large real-world PL/SQL corpus -- this is the
    # verbatim type declaration pair from alexandria-plsql-utils/ora/
    # amazon_aws_s3_pkg.pks (fetched directly from the upstream repo, not
    # paraphrased). A package SPEC (no BODY keyword) can itself declare a
    # local collection TYPE as part of its public interface -- ora2pg
    # mishandles it the same way as any other local collection type
    # (GAP-003), but object_name used to silently fall back to 'UNKNOWN'
    # since only PACKAGE BODY was recognized as an attribution container.
    source = """
    create or replace package amazon_aws_s3_pkg
    as
      type t_grantee is record (
        grantee_type varchar2(20),  -- CanonicalUser or Group
        user_id varchar2(200),      -- for users
        user_name varchar2(200),    -- for users
        group_uri varchar2(200),    -- for groups
        permission varchar2(20)     -- FULL_CONTROL, WRITE, READ_ACP
      );

      type t_grantee_list is table of t_grantee index by binary_integer;
      type t_grantee_tab is table of t_grantee;
    end amazon_aws_s3_pkg;
    """
    findings = find_bulk_collect_usage(source)
    assert len(findings) == 2
    assert {f.object_name for f in findings} == {"AMAZON_AWS_S3_PKG"}


def test_schema_level_create_type_is_not_flagged():
    # CREATE [OR REPLACE] TYPE ... IS TABLE OF ... (a column-usable
    # collection object type) is a different Oracle feature, not a local
    # DECLARE-section collection — out of scope for this detector.
    source = """
    CREATE OR REPLACE TYPE num_tab IS TABLE OF NUMBER;
    /
    CREATE TYPE another_tab IS TABLE OF VARCHAR2(100);
    /
    """
    assert find_bulk_collect_usage(source) == []


def test_schema_level_create_type_with_editionable_is_not_flagged():
    # EDITIONABLE/NONEDITIONABLE (Oracle 12c+) between 'OR REPLACE' and
    # 'TYPE' used to defeat the schema-level exclusion check, causing a
    # real schema-level collection type to be double-reported: correctly
    # by collection_type.py (GAP-021), and incorrectly by this detector
    # too, as if it were a local DECLARE-section collection.
    source = "CREATE OR REPLACE EDITIONABLE TYPE num_tab IS TABLE OF NUMBER;\n/\n"
    assert find_bulk_collect_usage(source) == []


def test_string_and_comment_content_does_not_trigger_false_positives():
    source = """
    create or replace procedure noop as
      v_text varchar2(200) := 'type t is table of number; bulk collect into x; forall i in 1..5';
    begin
      -- forall i in 1..5 loop null; end loop;
      null;
    end noop;
    /
    """
    assert find_bulk_collect_usage(source) == []


def test_plain_procedure_without_bulk_operations_is_not_flagged():
    source = """
    create or replace package body plain_pkg as
      procedure noop is
      begin
        null;
      end noop;
    end plain_pkg;
    /
    """
    assert find_bulk_collect_usage(source) == []


def test_package_name_does_not_leak_into_a_later_unrelated_standalone_routine():
    # enclosing_object_name() used to only reset its tracked package on a
    # new 'package' entry — a later standalone routine (which can't itself
    # be inside any package) didn't clear it, so a nested helper inside
    # that standalone routine got fabricated-attributed to the earlier,
    # unrelated package.
    source = """
    create or replace package body pkg1 as
      procedure proc_a is
      begin
        null;
      end proc_a;
    end pkg1;
    /
    create or replace procedure standalone_proc as
      procedure helper is
        type t_id_tab is table of number;
        v_ids t_id_tab;
      begin
        null;
      end helper;
    begin
      helper();
    end standalone_proc;
    /
    """
    findings = find_bulk_collect_usage(source)
    assert len(findings) == 1
    assert findings[0].object_name == "HELPER"


def test_create_type_with_a_long_comment_before_type_is_still_recognized_as_schema_level():
    # _is_schema_level_create_type used to only look back a fixed 40 chars
    # — a masked comment between CREATE OR REPLACE and TYPE longer than
    # that made it miss the CREATE prefix entirely.
    source = "CREATE OR REPLACE /* " + "x" * 100 + " */ TYPE num_tab IS TABLE OF NUMBER;\n/\n"
    assert find_bulk_collect_usage(source) == []
