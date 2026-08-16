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


def test_real_open_source_utplsql_bulk_collect_into_is_attributed():
    # Found scanning utPLSQL (github.com/utPLSQL/utPLSQL) — verbatim
    # excerpt of test/ut3_tester_helper/main_helper.pkb (see the matching
    # test in test_autonomous_tx.py for the same file's PRAGMA
    # AUTONOMOUS_TRANSACTION), exercising the BULK COLLECT INTO branch
    # specifically rather than the local TYPE...IS TABLE OF branch this
    # file's other real-corpus test (amazon_aws_s3_pkg.pks) already
    # covers.
    source = """
    create or replace package body main_helper is

      function run_test(a_path varchar2) return clob is
        l_lines    ut3_develop.ut_varchar2_list;
      begin
        select * bulk collect into l_lines from table(ut3_develop.ut.run(a_path));
        return ut3_develop.ut_utils.table_to_clob(l_lines);
      end;

    end main_helper;
    /
    """
    findings = find_bulk_collect_usage(source)
    assert len(findings) == 1
    assert findings[0].object_name == "MAIN_HELPER.RUN_TEST"
    assert findings[0].snippet == "bulk collect into"


def test_real_open_source_logger_install_script_anonymous_block_is_unknown_not_a_crash():
    # Found scanning OraOpenSource/Logger's install scripts — the full,
    # verbatim source/tables/logger_prefs_by_client_id.sql (not
    # paraphrased or trimmed, including its q'!...!'-quoted EXECUTE
    # IMMEDIATE strings, which is itself a real stress case for this
    # project's string-masking). A bare anonymous 'declare ... begin ...
    # end;' block used as a conditional "create table if not exists"
    # install script, not a named object. DBMS_METADATA.GET_DDL (this
    # project's documented Oracle export mechanism) exports named
    # objects, not free-standing anonymous blocks, so this shape is
    # outside this tool's documented scope — see enclosing_object_name()'s
    # docstring in plsql_lex.py. Kept as a permanent regression test not
    # because 'UNKNOWN' should become something more specific, but to lock
    # in that this shape is handled honestly (a clearly-labeled "don't
    # know", not a silent wrong guess or a crash) now that it's confirmed
    # to occur in real, shipped open-source Oracle code, not just
    # hypothetically.
    source = """
    declare
      l_count pls_integer;
      l_nullable user_tab_columns.nullable%type;

      type typ_required_columns is table of varchar2(30) index by pls_integer;
      l_required_columns typ_required_columns;

      l_sql varchar2(2000);

    begin
      -- Create Table
      select count(1)
      into l_count
      from user_tables
      where table_name = 'LOGGER_PREFS_BY_CLIENT_ID';

      if l_count = 0 then
        execute immediate q'!
    create table logger_prefs_by_client_id(
      client_id varchar2(64) not null,
      logger_level varchar2(20) not null,
      include_call_stack varchar2(5) not null,
      created_date date default sysdate not null,
      expiry_date date not null,
      constraint logger_prefs_by_client_id_pk primary key (client_id) enable,
      constraint logger_prefs_by_client_id_ck1 check (logger_level in ('OFF','PERMANENT','ERROR','WARNING','INFORMATION','DEBUG','TIMING')),
      constraint logger_prefs_by_client_id_ck2 check (expiry_date >= created_date),
      constraint logger_prefs_by_client_id_ck3 check (include_call_stack in ('TRUE', 'FALSE'))
    )
        !';
      end if;

      -- COMMENTS
      execute immediate q'!comment on table logger_prefs_by_client_id is 'Client specific logger levels. Only active client_ids/logger_levels will be maintained in this table'!';
      execute immediate q'!comment on column logger_prefs_by_client_id.client_id is 'Client identifier'!';
      execute immediate q'!comment on column logger_prefs_by_client_id.logger_level is 'Logger level. Must be OFF, PERMANENT, ERROR, WARNING, INFORMATION, DEBUG, TIMING'!';
      execute immediate q'!comment on column logger_prefs_by_client_id.include_call_stack is 'Include call stack in logging'!';
      execute immediate q'!comment on column logger_prefs_by_client_id.created_date is 'Date that entry was created on'!';
      execute immediate q'!comment on column logger_prefs_by_client_id.expiry_date is 'After the given expiry date the logger_level will be disabled for the specific client_id. Unless sepcifically removed from this table a job will clean up old entries'!';


      -- 92: Missing APEX and SYS_CONTEXT support
      l_sql := 'alter table logger_prefs_by_client_id drop constraint logger_prefs_by_client_id_ck1';
      execute immediate l_sql;

      -- Rebuild constraint
      l_sql := q'!alter table logger_prefs_by_client_id
        add constraint logger_prefs_by_client_id_ck1
        check (logger_level in ('OFF','PERMANENT','ERROR','WARNING','INFORMATION','DEBUG','TIMING', 'APEX', 'SYS_CONTEXT'))!';
      execute immediate l_sql;

    end;
    /
    """
    findings = find_bulk_collect_usage(source)
    assert len(findings) == 1
    assert findings[0].object_name == "UNKNOWN"


def test_real_open_source_utplsql_bulk_collect_hidden_inside_dynamic_sql_is_found():
    # Found scanning utPLSQL (github.com/utPLSQL/utPLSQL) with the dynamic-
    # SQL-visibility fix: test/ut3_tester_helper/coverage_helper.pkb's
    # run_code_as_job function builds an entire anonymous PL/SQL block --
    # including its own 'bulk collect into' -- as an EXECUTE IMMEDIATE
    # string argument, invisible to plain source scanning (masked as
    # string content) and, before this fix, silently missed entirely.
    #
    # Verbatim excerpt (not paraphrased) of coverage_helper.pkb's
    # run_code_as_job function, wrapped in a minimal package body using
    # the file's own real package name (coverage_helper.pkb line 1:
    # 'create or replace package body coverage_helper is').
    source = """
    create or replace package body coverage_helper is

  function run_code_as_job( a_plsql_block varchar2 ) return clob is
    l_result_clob clob;
    pragma autonomous_transaction;
  begin
    run_job_and_wait_for_finish( a_plsql_block );
    dbms_lock.sleep(0.1);
    execute immediate q'[
      declare
        l_results ut3_develop.ut_varchar2_list;
      begin
        select text
          bulk collect into l_results
          from test_results
         order by id;
        delete from test_results;
        commit;
        :clob_results := ut3_tester_helper.main_helper.table_to_clob(l_results);
      end;
      ]'
    using out l_result_clob;

    return l_result_clob;
  end;

    end coverage_helper;
    /
    """
    findings = find_bulk_collect_usage(source)
    assert len(findings) == 1
    # Attributed to the real, findable enclosing function in the static
    # source tree -- the dynamically-executed anonymous block itself has
    # no name of its own to attribute to at all.
    assert findings[0].object_name == "COVERAGE_HELPER.RUN_CODE_AS_JOB"
    assert findings[0].snippet == "bulk collect into"
