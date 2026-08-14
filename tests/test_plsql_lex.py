"""Regression tests for bugs found in code review of the shared lexer."""

from src.detectors.autonomous_tx import find_autonomous_transactions
from src.detectors.compound_triggers import find_compound_triggers
from src.plsql_lex import mask_strings_and_comments


def test_q_quote_literal_with_embedded_apostrophe_is_fully_masked():
    source = "v := q'[this isn't real code, just -- text with BEGIN inside]';"
    masked = mask_strings_and_comments(source)
    assert "isn" not in masked
    assert "BEGIN" not in masked
    assert masked.count("\n") == source.count("\n")
    assert len(masked) == len(source)


def test_q_quote_does_not_cause_false_positive_compound_trigger():
    source = """
    create or replace trigger trg_q
      before insert on employees
    begin
      v_msg varchar2(100) := q'[this isn't a compound trigger, just text]';
      null;
    end trg_q;
    /
    """
    assert find_compound_triggers(source) == []


def test_q_quote_does_not_hide_a_real_pragma():
    source = """
    create or replace package body demo as
      procedure foo is
        c_msg constant varchar2(50) := q'[isn't this fun]';
        pragma autonomous_transaction;
      begin
        commit;
      end foo;
    end demo;
    /
    """
    findings = find_autonomous_transactions(source)
    assert {f.object_name for f in findings} == {"DEMO.FOO"}


def test_dollar_and_hash_are_legal_in_unquoted_identifiers():
    source = """
    create or replace trigger trg$audit#1
      before insert on employees
      compound trigger
      before statement is
      begin
        null;
      end before statement;
    end trg$audit#1;
    /
    """
    findings = find_compound_triggers(source)
    assert {f.object_name for f in findings} == {"TRG$AUDIT#1"}
