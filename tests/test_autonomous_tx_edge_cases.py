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
