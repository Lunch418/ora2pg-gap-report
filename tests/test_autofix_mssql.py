"""The two mechanical MSSQL fixes, and the per-dialect fixer registry.

Both fixers were validated against real ora2pg 25.0 -M output loaded into
a live PostgreSQL 16 (see each one's research doc); what these tests pin
down is the boundary -- that they undo exactly the broken shape and leave
every valid neighbouring construct alone.
"""

from ora2pg_gap_report.autofix import (
    FIXERS_BY_DIALECT,
    fix_identity_double_parens,
    fix_mssql_charindex_quotes,
    fix_mssql_empty_declare,
)
from ora2pg_gap_report.core import DIALECTS


def test_the_fixer_registry_covers_every_dialect():
    # A dialect missing here would make --fix raise a KeyError instead of
    # saying it has no fixes for it.
    assert set(FIXERS_BY_DIALECT) == set(DIALECTS)


def test_mysql_has_no_fixers_on_purpose():
    # Documented in autofix.py: every confirmed MySQL gap needs either a
    # design decision or data the generated file no longer carries.
    assert FIXERS_BY_DIALECT["mysql"] == ()


def test_oracle_keeps_exactly_its_one_fixer():
    assert FIXERS_BY_DIALECT["oracle"] == (fix_identity_double_parens,)


# --- CHARINDEX -> position(), with ora2pg's doubled quotes (GAP-100) ---


def test_doubled_quotes_around_the_needle_are_undone():
    # Verbatim from a real `ora2pg -M -t PROCEDURE` run.
    source = "     SELECT  position(''abc'' in p_nm);\n"
    fixed, count = fix_mssql_charindex_quotes(source)
    assert count == 1
    assert fixed == "     SELECT  position('abc' in p_nm);\n"


def test_the_fix_preserves_surrounding_whitespace_byte_for_byte():
    # The diff must show only the quotes changing -- nothing else.
    source = "SELECT position(  ''x''   in  nm);"
    fixed, _ = fix_mssql_charindex_quotes(source)
    assert fixed == "SELECT position(  'x'   in  nm);"


def test_two_calls_are_both_fixed():
    source = "SELECT position(''a'' in x), position(''b'' in y);"
    fixed, count = fix_mssql_charindex_quotes(source)
    assert count == 2
    assert "''" not in fixed


def test_a_search_for_the_empty_string_is_left_alone():
    # position('' in x) is valid, if pointless -- an empty needle never
    # matches the broken shape.
    source = "SELECT position('' in nm);"
    assert fix_mssql_charindex_quotes(source) == (source, 0)


def test_a_literal_containing_an_escaped_quote_is_left_alone():
    # 'a''b' is one valid literal, not the doubled-quote bug.
    source = "SELECT position('a''b' in nm);"
    assert fix_mssql_charindex_quotes(source) == (source, 0)


def test_an_already_correct_call_is_left_alone():
    source = "SELECT position('abc' in nm);"
    assert fix_mssql_charindex_quotes(source) == (source, 0)


# --- the empty DECLARE block of a parameterless procedure (GAP-091) ---


def test_the_empty_declare_block_is_removed():
    # Verbatim from a real `ora2pg -M -t PROCEDURE` run on a procedure
    # that takes no parameters.
    source = (
        "CREATE OR REPLACE PROCEDURE dbo.clean_np () AS $body$\n"
        "DECLARE\n"
        "\n"
        ";\n"
        "BEGIN\n"
        "     INSERT  INTO orders(nm) VALUES ('x');\n"
        "END;\n"
    )
    fixed, count = fix_mssql_empty_declare(source)
    assert count == 1
    assert fixed == (
        "CREATE OR REPLACE PROCEDURE dbo.clean_np () AS $body$\n"
        "BEGIN\n"
        "     INSERT  INTO orders(nm) VALUES ('x');\n"
        "END;\n"
    )


def test_a_declare_block_with_real_variables_is_left_alone():
    source = "DECLARE\n  v_total integer;\nBEGIN\n  NULL;\nEND;\n"
    assert fix_mssql_empty_declare(source) == (source, 0)


def test_a_declare_whose_variable_follows_a_blank_line_is_left_alone():
    # ora2pg emits this shape too (a blank line, then a real declaration);
    # only the lone-semicolon form is the bug.
    source = "DECLARE\n\ncur_balance decimal(12,2);\nBEGIN\n"
    assert fix_mssql_empty_declare(source) == (source, 0)


def test_a_procedure_that_never_had_a_declare_is_left_alone():
    source = "CREATE OR REPLACE PROCEDURE dbo.p (p_x integer) AS $body$\nBEGIN\n  NULL;\nEND;\n"
    assert fix_mssql_empty_declare(source) == (source, 0)


def test_two_parameterless_procedures_in_one_file_are_both_fixed():
    source = (
        "CREATE OR REPLACE PROCEDURE a () AS $body$\nDECLARE\n\n;\nBEGIN\n  NULL;\nEND;\n$body$;\n"
        "CREATE OR REPLACE PROCEDURE b () AS $body$\nDECLARE\n\n;\nBEGIN\n  NULL;\nEND;\n$body$;\n"
    )
    fixed, count = fix_mssql_empty_declare(source)
    assert count == 2
    assert "DECLARE" not in fixed


def test_the_two_mssql_fixers_compose_on_one_file():
    # --fix chains every fixer for the dialect, so a file carrying both
    # bugs comes out with both undone in a single pass.
    source = (
        "CREATE OR REPLACE PROCEDURE dbo.p () AS $body$\n"
        "DECLARE\n"
        "\n"
        ";\n"
        "BEGIN\n"
        "  SELECT position(''abc'' in nm);\n"
        "END;\n"
    )
    fixed = source
    total = 0
    for fixer in FIXERS_BY_DIALECT["mssql"]:
        fixed, applied = fixer(fixed)
        total += applied
    assert total == 2
    assert "DECLARE" not in fixed
    assert "position('abc' in nm)" in fixed
