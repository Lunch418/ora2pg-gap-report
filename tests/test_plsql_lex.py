"""Regression tests for bugs found in code review of the shared lexer."""

import pytest

from ora2pg_gap_report.detectors.autonomous_tx import find_autonomous_transactions
from ora2pg_gap_report.detectors.compound_triggers import find_compound_triggers
from ora2pg_gap_report.plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    mask_dynamic_sql_visible,
    mask_strings_and_comments,
)


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


def test_package_spec_is_recognized_as_an_attribution_container():
    # Found by scanning a large real-world PL/SQL corpus
    # (alexandria-plsql-utils): a bare package spec ('CREATE [OR REPLACE]
    # PACKAGE name IS/AS', no BODY keyword) declares its own local
    # constructs too (e.g. a public collection TYPE) -- these used to
    # silently attribute to 'UNKNOWN' because only PACKAGE BODY was
    # recognized as a 'package' container.
    source = """
    create or replace package amazon_aws_s3_pkg as
      type t_grantee_list is table of number index by binary_integer;
    end amazon_aws_s3_pkg;
    """
    clean = mask_strings_and_comments(source)
    index = enclosing_object_name_index(clean)
    type_decl_pos = clean.index("type t_grantee_list")
    assert enclosing_object_name(index, type_decl_pos) == "AMAZON_AWS_S3_PKG"


def test_package_spec_and_package_body_in_the_same_file_are_both_recognized():
    # A common real export shape: PACKAGE (spec) followed by PACKAGE BODY
    # for the same name in one file. Each must attribute constructs
    # nested under it to its own occurrence, not bleed into the other.
    source = """
    create or replace package demo_pkg as
      type t_spec_local is table of number;
    end demo_pkg;
    /
    create or replace package body demo_pkg as
      procedure noop is
        type t_body_local is table of number;
      begin
        null;
      end noop;
    end demo_pkg;
    /
    """
    clean = mask_strings_and_comments(source)
    index = enclosing_object_name_index(clean)
    spec_local_pos = clean.index("type t_spec_local")
    body_local_pos = clean.index("type t_body_local")
    assert enclosing_object_name(index, spec_local_pos) == "DEMO_PKG"
    assert enclosing_object_name(index, body_local_pos) == "DEMO_PKG.NOOP"


def test_package_spec_regex_does_not_double_match_a_package_body_declaration():
    # The negative lookahead in _PACKAGE_SPEC_NAME_RE must keep 'PACKAGE
    # BODY name' from also being indexed a second time as a spurious
    # 'package' entry at the same position.
    source = "create or replace package body demo_pkg as\nend demo_pkg;\n/\n"
    clean = mask_strings_and_comments(source)
    index = enclosing_object_name_index(clean)
    package_entries = [e for e in index if e[1] == "package"]
    assert len(package_entries) == 1
    assert package_entries[0][2] == "DEMO_PKG"


def test_grant_statement_privilege_list_is_not_treated_as_a_view_declaration():
    # Real line from oracle-samples/db-sample-schemas: 'CREATE VIEW' as a
    # two-word privilege name inside a GRANT list must not be captured as
    # if 'TO' (the next word) were a real view name.
    source = "GRANT CREATE SESSION, CREATE SYNONYM, CREATE VIEW TO oe;\n"
    clean = mask_strings_and_comments(source)
    assert enclosing_object_name_index(clean) == ()


def test_revoke_statement_privilege_list_is_not_treated_as_a_declaration():
    source = "REVOKE CREATE VIEW FROM oe;\n"
    clean = mask_strings_and_comments(source)
    assert enclosing_object_name_index(clean) == ()


def test_create_statement_preceded_by_an_unterminated_sqlplus_command_is_still_recognized():
    # A stricter earlier version of the GRANT-list fix required CREATE to
    # be the literal first token of its own statement (immediately after
    # ';'/'/' /start-of-text) -- that broke on real input, since SQL*Plus
    # client commands (SET, PROMPT, @script, DEFINE, WHENEVER) routinely
    # precede a real CREATE and are themselves terminated by a bare
    # newline, not ';' or '/'. Exact real shape from oracle-samples/
    # db-sample-schemas/human_resources/hr_code.sql.
    source = "SET ECHO OFF\n\nCREATE OR REPLACE PROCEDURE secure_dml AS\nBEGIN\n  NULL;\nEND;\n/\n"
    clean = mask_strings_and_comments(source)
    index = enclosing_object_name_index(clean)
    assert [e for e in index if e[1] == "standalone_routine"] == [
        (index[0][0], "standalone_routine", "SECURE_DML")
    ]


def test_view_preceded_by_prompt_command_is_still_recognized():
    source = "Prompt some descriptive text\n\nCREATE OR REPLACE VIEW emp_details_view AS SELECT 1 FROM dual;\n"
    clean = mask_strings_and_comments(source)
    index = enclosing_object_name_index(clean)
    assert [e for e in index if e[1] == "view"][0][2] == "EMP_DETAILS_VIEW"


def test_rem_line_comment_is_masked():
    # SQL*Plus's REM/REMARK line comment -- found via a real-world corpus
    # (oracle-samples/db-sample-schemas): a CREATE VIEW preceded only by
    # REM comment lines used to fail _is_statement_start()'s scan back to
    # the previous ';' because REM lines were never masked, corrupting the
    # view's own attribution back to 'UNKNOWN'.
    source = "rem this is a comment\nx := 1;\n"
    masked = mask_strings_and_comments(source)
    assert "comment" not in masked
    assert "x := 1;" in masked


def test_remark_long_form_is_also_masked():
    source = "remark this is a comment\nx := 1;\n"
    masked = mask_strings_and_comments(source)
    assert "comment" not in masked


def test_rem_is_only_a_comment_at_the_start_of_a_line():
    # 'REM' as an ordinary identifier prefix mid-statement must survive.
    source = "rem_var := 1;\n"
    masked = mask_strings_and_comments(source)
    assert "rem_var" in masked


def test_word_starting_with_rem_is_not_treated_as_a_comment():
    # REMOTE_TABLE at the start of a line is a real identifier, not REM
    # followed by more text -- the lookahead must require a boundary.
    source = "remote_table_name number,\n"
    masked = mask_strings_and_comments(source)
    assert "remote_table_name" in masked


def test_indented_rem_comment_is_masked():
    source = "  rem indented comment\nx := 1;\n"
    masked = mask_strings_and_comments(source)
    assert "comment" not in masked


def test_view_preceded_only_by_rem_comments_is_correctly_attributed():
    # The exact real-world shape found in oracle-samples/db-sample-schemas
    # customer_orders/co_create.sql.
    source = """
    CREATE TABLE t (id NUMBER);

    rem ********************************************************************
    rem A relational view of something

    CREATE OR REPLACE VIEW product_reviews AS
      SELECT rating FROM JSON_TABLE(x, '$' COLUMNS (rating NUMBER PATH '$.r'));
    """
    clean = mask_strings_and_comments(source)
    index = enclosing_object_name_index(clean)
    view_pos = clean.index("JSON_TABLE")
    assert enclosing_object_name(index, view_pos) == "PRODUCT_REVIEWS"


def test_mask_dynamic_sql_visible_reveals_single_literal_execute_immediate_argument():
    source = "execute immediate 'select connect by nocycle x from t';"
    visible = mask_dynamic_sql_visible(source)
    assert "CONNECT BY NOCYCLE" in visible.upper()
    assert len(visible) == len(source)
    assert visible.count("\n") == source.count("\n")


def test_mask_dynamic_sql_visible_reveals_concatenated_literal_segments():
    source = "execute immediate 'select ' || v_col || ' bulk collect into l_x from t';"
    visible = mask_dynamic_sql_visible(source)
    assert "BULK COLLECT INTO" in visible.upper()


def test_mask_dynamic_sql_visible_reveals_q_quote_argument():
    source = "execute immediate q'[create table t partition by range (d) (partition p1 values less than (1))]';"
    visible = mask_dynamic_sql_visible(source)
    assert "PARTITION BY RANGE" in visible.upper()


def test_mask_dynamic_sql_visible_stops_at_the_bare_terminating_semicolon():
    source = "execute immediate 'select 1 from dual'; v_x := 'pivot for col in (1,2)';"
    visible = mask_dynamic_sql_visible(source)
    # The EXECUTE IMMEDIATE argument is revealed, but an ordinary string
    # assignment afterwards -- not itself dynamic SQL -- is still masked.
    assert "PIVOT" not in visible.upper()


def test_mask_dynamic_sql_visible_leaves_ordinary_strings_and_comments_masked():
    source = "-- a comment mentioning pivot\nv_x := 'a string mentioning cross apply';"
    visible = mask_dynamic_sql_visible(source)
    assert "PIVOT" not in visible.upper()
    assert "CROSS APPLY" not in visible.upper()


def test_mask_dynamic_sql_visible_does_not_crash_on_unterminated_execute_immediate():
    source = "execute immediate 'select 1 from dual"  # no closing quote, no ';'
    visible = mask_dynamic_sql_visible(source)
    assert len(visible) == len(source)


def test_dynamic_sql_that_creates_a_package_at_runtime_is_not_picked_up_as_a_real_container():
    # The container/attribution index (enclosing_object_name_index) must
    # always be built from the safe, fully-masked view -- never from a view
    # where dynamic SQL is left visible -- or a package a routine creates
    # dynamically at runtime (never actually declared in the static source
    # tree) would be picked up as if it were a real enclosing object,
    # misattributing unrelated findings to a name a developer could never
    # find by searching the codebase. See autonomous_tx.py's and each
    # two-view detector's own module docstring for the full reasoning.
    source = """
    create or replace package body outer_pkg is
      procedure build_it is
      begin
        execute immediate 'create or replace package body fake_pkg as
          procedure inner_proc is
          begin
            null;
          end;
        end;';
      end;
    end outer_pkg;
    /
    """
    safe = mask_strings_and_comments(source)
    index = enclosing_object_name_index(safe)
    names = {name for _, _, name in index}
    assert "FAKE_PKG" not in names
    assert names == {"OUTER_PKG", "BUILD_IT"}


def test_masking_and_index_functions_are_cached_across_equal_calls():
    # ~37 detectors each call mask_strings_and_comments() with the exact
    # same `source` for a given scanned file (a third of them also call
    # mask_dynamic_sql_visible()/enclosing_object_name_index()) -- scanning
    # one file used to redo all of this same O(n) work ~2-3 dozen times
    # over. Caching collapses that to one real computation per distinct
    # input; `is` (not just `==`) proves the *same* cached object comes
    # back on a second call with an equal string, not just an equal one.
    source = "create or replace package body pkg as\n  procedure noop is\n  begin null; end;\nend pkg;\n"
    assert mask_strings_and_comments(source) is mask_strings_and_comments(source)
    assert mask_dynamic_sql_visible(source) is mask_dynamic_sql_visible(source)

    clean = mask_strings_and_comments(source)
    assert enclosing_object_name_index(clean) is enclosing_object_name_index(clean)


def test_enclosing_object_name_index_returns_an_immutable_tuple():
    # Its result is shared (the same cached object) across every caller
    # that scans the same masked text -- a list would let one caller's
    # accidental in-place mutation (.append()/.sort()/...) silently
    # corrupt what every other caller sees. A tuple makes that a type
    # error instead of a shared-mutable-state bug.
    index = enclosing_object_name_index("create or replace package body pkg as\nend pkg;\n")
    assert isinstance(index, tuple)
    with pytest.raises(AttributeError):
        index.append((0, "package", "X"))  # type: ignore[attr-defined]
