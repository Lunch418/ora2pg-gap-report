"""Regression tests for bugs found in code review (see git log) before this
module existed: nested subprograms, string/comment-unaware scanning, and
multiple package bodies in one file."""

from ora2pg_gap_report.detectors.autonomous_tx import find_autonomous_transactions


def test_outer_pragma_survives_a_nested_subprogram_before_it():
    source = """
    create or replace package body demo as
      procedure outer_proc is
        pragma autonomous_transaction;
        procedure nested_proc is
        begin
          null;
        end nested_proc;
      begin
        commit;
      end outer_proc;
    end demo;
    /
    """
    findings = find_autonomous_transactions(source)
    assert {f.object_name for f in findings} == {"DEMO.OUTER_PROC"}


def test_nested_subprograms_pragma_is_not_reported_as_top_level():
    source = """
    create or replace package body demo as
      procedure outer_proc is
        procedure nested_proc is
          pragma autonomous_transaction;
        begin
          commit;
        end nested_proc;
      begin
        nested_proc();
      end outer_proc;
    end demo;
    /
    """
    findings = find_autonomous_transactions(source)
    assert findings == []


def test_string_literal_containing_double_dash_does_not_eat_following_pragma():
    source = """
    create or replace package body demo as
      procedure foo is
        c_sep constant varchar2(20) := '--x'; pragma autonomous_transaction;
      begin
        commit;
      end foo;
    end demo;
    /
    """
    findings = find_autonomous_transactions(source)
    assert {f.object_name for f in findings} == {"DEMO.FOO"}


def test_string_literal_containing_begin_does_not_truncate_declare_section():
    source = """
    create or replace package body demo as
      procedure foo is
        c_msg constant varchar2(30) := 'BEGIN NOW';
        pragma autonomous_transaction;
      begin
        commit;
      end foo;
    end demo;
    /
    """
    findings = find_autonomous_transactions(source)
    assert {f.object_name for f in findings} == {"DEMO.FOO"}


def test_multiple_package_bodies_in_one_file_get_correct_package_names():
    source = """
    create or replace package body pkg_a as
      procedure a1 is begin null; end a1;
    end pkg_a;
    /
    create or replace package body pkg_b as
      procedure foo is
        pragma autonomous_transaction;
      begin
        commit;
      end foo;
    end pkg_b;
    /
    """
    findings = find_autonomous_transactions(source)
    assert {f.object_name for f in findings} == {"PKG_B.FOO"}


def test_case_expression_end_does_not_confuse_block_matching():
    source = """
    create or replace package body demo as
      procedure foo is
        pragma autonomous_transaction;
        v_flag integer;
      begin
        select case when 1 = 1 then 1 else 0 end into v_flag from dual;
        commit;
      end foo;
    end demo;
    /
    """
    findings = find_autonomous_transactions(source)
    assert {f.object_name for f in findings} == {"DEMO.FOO"}


def test_if_and_loop_blocks_do_not_confuse_block_matching():
    source = """
    create or replace package body demo as
      procedure foo is
        pragma autonomous_transaction;
      begin
        for i in 1..3 loop
          if i = 2 then
            null;
          end if;
        end loop;
        commit;
      end foo;
    end demo;
    /
    """
    findings = find_autonomous_transactions(source)
    assert {f.object_name for f in findings} == {"DEMO.FOO"}


def test_pragma_before_a_forward_declared_nested_procedures_real_body_is_not_swallowed():
    # A forward declaration ('procedure helper;', used to allow mutual
    # recursion between private nested subprograms) has no IS/AS of its
    # own. _find_own_begin used to search forward for the next IS/AS
    # regardless, land on the *real* body's IS/AS declared later, and treat
    # everything from the forward declaration through that real body's end
    # as one nested span to blank out — silently erasing outer_proc's own
    # PRAGMA AUTONOMOUS_TRANSACTION, which sits in between, along the way.
    source = """
    create or replace package body pkg1 as
      procedure outer_proc is
        procedure helper;
        pragma autonomous_transaction;
        procedure helper is begin null; end helper;
      begin
        helper();
        commit;
      end outer_proc;
    end pkg1;
    /
    """
    findings = find_autonomous_transactions(source)
    assert {f.object_name for f in findings} == {"PKG1.OUTER_PROC"}


def test_pragma_in_a_routine_after_a_package_level_forward_declaration_is_not_lost():
    # Same bug class as the nested case above, but at PACKAGE BODY scope:
    # declare_and_begin used to search forward for the next IS/AS
    # unconditionally, so a package-level forward declaration ('procedure
    # helper;') would make it land on the *next* routine's IS/AS and
    # misattribute that routine's entire body (including its own PRAGMA) to
    # the forward-declared name instead.
    source = """
    create or replace package body pkg as
      procedure helper;
      procedure caller is
        pragma autonomous_transaction;
      begin
        helper();
        commit;
      end caller;
      procedure helper is
      begin
        null;
      end helper;
    end pkg;
    /
    """
    findings = find_autonomous_transactions(source)
    assert {f.object_name for f in findings} == {"PKG.CALLER"}
