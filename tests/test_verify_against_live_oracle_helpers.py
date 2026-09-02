"""Tests for the pure, Oracle-free parts of
scripts/verify_against_live_oracle.py — the part that actually needs a
live Oracle instance is out of scope for this test suite by design (see
README's "Проверка на живой Oracle" section); this covers what can be
verified without one: splitting real SQL*Plus-style fixture files into
individual statements."""

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "verify_against_live_oracle.py"
SAMPLES = Path(__file__).resolve().parents[1] / "docs" / "research" / "samples"


def _load_module():
    spec = importlib.util.spec_from_file_location("verify_against_live_oracle", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verify = _load_module()


def test_single_statement_file_with_trailing_slash():
    text = "create or replace package body x as\nend;\n/\n"
    assert verify.split_sql_statements(text) == ["create or replace package body x as\nend;"]


def test_falls_back_to_semicolon_splitting_when_no_slash_separators():
    text = "create table a (id number);\ncreate table b (id number);"
    stmts = verify.split_sql_statements(text)
    assert stmts == ["create table a (id number)", "create table b (id number)"]


def test_real_logger_pkb_is_a_single_statement():
    text = (SAMPLES / "logger.pkb").read_text(encoding="utf-8")
    stmts = verify.split_sql_statements(text)
    assert len(stmts) == 1
    assert stmts[0].lower().startswith("create or replace package body logger")


def test_real_compound_trigger_apress_is_a_single_statement():
    text = (SAMPLES / "compound_trigger_apress.sql").read_text(encoding="utf-8")
    stmts = verify.split_sql_statements(text)
    assert len(stmts) == 1
    assert "compound trigger" in stmts[0].lower()


def test_real_dlee_file_captures_the_compound_trigger_targeting_mfe_customers():
    # This file mixes comments, an ordinary trigger, two anonymous PL/SQL
    # blocks, a package, three plain triggers, a DROP TRIGGER, and (at the
    # end) the one COMPOUND TRIGGER our detector actually cares about —
    # real-world messiness the splitter has to get right, not a clean
    # synthetic case.
    text = (SAMPLES / "compound_trigger_dlee.sql").read_text(encoding="utf-8")
    stmts = verify.split_sql_statements(text)

    compound_chunks = [s for s in stmts if "compound trigger" in s.lower()]
    assert len(compound_chunks) == 1
    assert "mfe_customers" in compound_chunks[0].lower()
    assert "equitable_salary_trg" in compound_chunks[0].lower()


def test_a_lone_slash_inside_a_comment_does_not_split_the_statement():
    # A '/*...*/' comment illustrating division (or any divider using '/'
    # on its own line) must not be mistaken for a SQL*Plus statement
    # terminator — this must reuse the same comment-masking the detectors
    # use, not a naive line-by-line "/" check.
    text = (
        "create or replace package body demo as\n"
        "/*\n"
        "division example:\n"
        "a\n"
        "/\n"
        "b\n"
        "*/\n"
        "  procedure noop is\n"
        "  begin\n"
        "    null;\n"
        "  end noop;\n"
        "end demo;\n"
        "/\n"
    )
    stmts = verify.split_sql_statements(text)
    assert len(stmts) == 1
    assert "end demo;" in stmts[0]


def test_trailing_comment_only_chunk_is_not_treated_as_a_statement():
    # A trailing attribution/license comment block with no code after it
    # (as docs/research/samples/compound_trigger_dlee.sql actually has)
    # must be dropped, not handed to cursor.execute() as if it were SQL.
    text = (
        "create or replace package body demo as\n"
        "  procedure noop is begin null; end noop;\n"
        "end demo;\n"
        "/\n"
        "\n"
        "/*\n"
        "Copyright someone, some year. All rights reserved.\n"
        "*/\n"
    )
    stmts = verify.split_sql_statements(text)
    assert len(stmts) == 1
    assert "Copyright" not in stmts[0]


def test_real_dlee_file_has_no_trailing_comment_only_statement():
    text = (SAMPLES / "compound_trigger_dlee.sql").read_text(encoding="utf-8")
    stmts = verify.split_sql_statements(text)
    assert "Supplement to the fifth edition" not in stmts[-1]


def test_dsn_regex_parses_host_port_service():
    import re

    match = re.match(r"^([^:/]+)(?::(\d+))?/(.+)$", "localhost:1521/FREEPDB1")
    assert match.groups() == ("localhost", "1521", "FREEPDB1")


def test_dsn_regex_defaults_missing_port_to_none():
    import re

    match = re.match(r"^([^:/]+)(?::(\d+))?/(.+)$", "localhost/FREEPDB1")
    assert match.groups() == ("localhost", None, "FREEPDB1")
