"""--prepare: the source rewrites that let ora2pg convert what it otherwise
gets wrong.

Three levels, for the same nine cases:
- what each rewrite does to the text, and what it leaves alone;
- under the `ora2pg` marker, that the real ora2pg still mangles the
  original and converts the prepared source (this is what would notice an
  ora2pg release that fixes a gap upstream, or breaks a rewrite);
- under the `docker` marker, that ora2pg's real output for the prepared
  source -- recorded in tests/fixtures/prepare/ -- loads into PostgreSQL
  16 and behaves, checked with ASSERTs.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ora2pg_gap_report.cli import main
from ora2pg_gap_report.prepare import (
    PREPARER_DETECTOR,
    PREPARERS_BY_DIALECT,
    prepare_mssql_brackets,
    prepare_mysql_definer,
    prepare_mysql_delimiter,
    prepare_mysql_table_if_not_exists,
    prepare_mysql_versioned_comments,
    prepare_oracle_alt_quote,
    prepare_oracle_table_if_not_exists,
)

FIXTURES = Path(__file__).parent / "fixtures" / "prepare"

# name: (dialect, ora2pg -t type, source, what ora2pg must produce from the
# prepared source, PostgreSQL to run before it, PostgreSQL that checks it)
CASES = {
    "g106_function": (
        "mysql",
        "FUNCTION",
        "DELIMITER //\nCREATE FUNCTION add_one(p INT) RETURNS int DETERMINISTIC\nBEGIN\n  RETURN p + 1;\nEND //\nDELIMITER ;\n",
        "CREATE OR REPLACE FUNCTION add_one",
        "",
        "DO $$ BEGIN ASSERT add_one(1) = 2; END $$;",
    ),
    "g107_trigger": (
        "mysql",
        "TRIGGER",
        "DELIMITER //\nCREATE TRIGGER t_bi BEFORE INSERT ON t FOR EACH ROW\nBEGIN\n  SET NEW.b = NEW.a;\nEND //\nDELIMITER ;\n",
        "CREATE TRIGGER t_bi",
        "CREATE TABLE t (a int, b int);",
        "INSERT INTO t (a) VALUES (5); DO $$ BEGIN ASSERT (SELECT b FROM t) = 5; END $$;",
    ),
    "g108_definer": (
        "mysql",
        "PROCEDURE",
        "DELIMITER ;;\nCREATE DEFINER=`app`@`%` PROCEDURE `close_order`(p_id INT)\nBEGIN\n"
        "  UPDATE orders SET status = 'closed' WHERE id = p_id;\nEND ;;\nDELIMITER ;\n",
        "CREATE OR REPLACE PROCEDURE close_order",
        "CREATE TABLE orders (id int, status text); INSERT INTO orders VALUES (1, 'open');",
        "CALL close_order(1); DO $$ BEGIN ASSERT (SELECT status FROM orders) = 'closed'; END $$;",
    ),
    "g109_versioned_trigger": (
        "mysql",
        "TRIGGER",
        "DELIMITER ;;\n/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `trg` "
        "BEFORE UPDATE ON `language` FOR EACH ROW BEGIN\n  SET NEW.name = UPPER(NEW.name);\nEND */;;\nDELIMITER ;\n",
        "CREATE TRIGGER trg",
        "CREATE TABLE language (id int, name text); INSERT INTO language VALUES (1, 'x');",
        "UPDATE language SET name = 'abc'; DO $$ BEGIN ASSERT (SELECT name FROM language) = 'ABC'; END $$;",
    ),
    "g109_versioned_view": (
        "mysql",
        "VIEW",
        "/*!50001 CREATE ALGORITHM=UNDEFINED */\n/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */\n"
        "/*!50001 VIEW `v_probe` AS select 1 AS `x` */;\n",
        "CREATE OR REPLACE VIEW v_probe",
        "",
        "DO $$ BEGIN ASSERT (SELECT x FROM v_probe) = 1; END $$;",
    ),
    "g110_if_not_exists": (
        "mysql",
        "TABLE",
        "CREATE TABLE IF NOT EXISTS `customers` (\n  `id` int NOT NULL,\n  `name` varchar(50) DEFAULT NULL,\n"
        "  PRIMARY KEY (`id`)\n) ENGINE=InnoDB;\n",
        "CREATE TABLE customers",
        "",
        "INSERT INTO customers VALUES (1, 'a');",
    ),
    "g062_alt_quote": (
        "oracle",
        "PROCEDURE",
        "CREATE OR REPLACE PROCEDURE say_it IS\n  v VARCHAR2(100);\nBEGIN\n  v := q'[it's here]';\n"
        "  INSERT INTO said VALUES (v);\nEND;\n/\n",
        "v := 'it''s here';",
        "CREATE TABLE said (v text);",
        "CALL say_it(); DO $$ BEGIN ASSERT (SELECT v FROM said) = 'it''s here'; END $$;",
    ),
    "g112_if_not_exists": (
        "oracle",
        "TABLE",
        "CREATE TABLE IF NOT EXISTS customers (\n  id NUMBER(10) NOT NULL,\n  name VARCHAR2(50)\n);\n",
        "CREATE TABLE customers",
        "",
        "INSERT INTO customers VALUES (1, 'a');",
    ),
    "g087_brackets": (
        "mssql",
        "TABLE",
        "CREATE TABLE [dbo].[Orders](\n    [Id] [int] IDENTITY(1,1) NOT NULL,\n"
        "    [CustomerName] [nvarchar](100) NOT NULL,\n    [Total] [money] NULL,\n"
        " CONSTRAINT [PK_Orders] PRIMARY KEY CLUSTERED ([Id] ASC)\n);\n",
        "CREATE TABLE dbo.orders",
        "CREATE SCHEMA IF NOT EXISTS dbo;",
        "INSERT INTO dbo.orders (id, customername) VALUES (1, 'a');",
    ),
    "g126_go_separator": (
        "mssql",
        "PROCEDURE",
        "CREATE PROCEDURE add_order @id int\nAS\nBEGIN\n    INSERT INTO orders (id) VALUES (@id);\nEND\nGO\n"
        "CREATE FUNCTION next_id (@a int) RETURNS int\nAS\nBEGIN\n    RETURN @a + 1;\nEND\nGO\n",
        "CREATE OR REPLACE PROCEDURE add_order",
        "CREATE TABLE orders (id int);",
        "CALL add_order(5);\nDO $$ BEGIN ASSERT next_id(1) = 2 AND (SELECT id FROM orders) = 5; END $$;",
    ),
}


# Where ora2pg does produce the object from the original, but broken: what
# in its output shows it. Elsewhere the object is missing altogether.
BROKEN_SIGN = {
    "g106_function": "END //",  # the delimiter leaks into the body
    "g126_go_separator": "\nGO\n",  # the batch separator leaks into the body
}


def _prepared(dialect, source):
    for preparer in PREPARERS_BY_DIALECT[dialect]:
        source, _ = preparer(source)
    return source


# --- the rewrites themselves --------------------------------------------------


def test_delimiter_blocks_become_plain_statements():
    source = "DELIMITER //\nCREATE FUNCTION f() RETURNS int\nBEGIN\n  RETURN 1; -- not // here\nEND //\nDELIMITER ;\nSELECT '//';\n"
    fixed, count = prepare_mysql_delimiter(source)
    assert count == 1
    assert fixed == "CREATE FUNCTION f() RETURNS int\nBEGIN\n  RETURN 1; -- not // here\nEND ;\nSELECT '//';\n"


def test_delimiter_inside_a_string_is_text():
    source = "SELECT 'DELIMITER //';\n"
    assert prepare_mysql_delimiter(source) == (source, 0)


def test_definer_goes_but_not_from_strings():
    source = "CREATE DEFINER=`app`@`%` PROCEDURE p() SELECT 'DEFINER=`x`@`y`';"
    assert prepare_mysql_definer(source) == ("CREATE PROCEDURE p() SELECT 'DEFINER=`x`@`y`';", 1)
    assert prepare_mysql_definer("CREATE DEFINER = CURRENT_USER VIEW v AS SELECT 1;")[0] == "CREATE VIEW v AS SELECT 1;"


def test_only_version_comments_around_definitions_are_unwrapped():
    source = "/*!40101 SET NAMES utf8 */;\n/*!50001 CREATE ALGORITHM=UNDEFINED */\n/*!50001 VIEW `v` AS select 1 */;\n"
    fixed, count = prepare_mysql_versioned_comments(source)
    assert count == 2
    # the session setting stays a comment; the definition is one line
    assert fixed == "/*!40101 SET NAMES utf8 */;\nCREATE ALGORITHM=UNDEFINED VIEW `v` AS select 1;\n"


def test_if_not_exists_is_dropped_in_code_only():
    source = "CREATE TABLE IF NOT EXISTS `t` (id int); -- CREATE TABLE IF NOT EXISTS x\n"
    assert prepare_mysql_table_if_not_exists(source) == ("CREATE TABLE `t` (id int); -- CREATE TABLE IF NOT EXISTS x\n", 1)
    assert prepare_oracle_table_if_not_exists("create table if not exists t (id number);") == (
        "create table t (id number);",
        1,
    )


def test_alt_quote_becomes_the_literal_it_spells():
    source = "v := q'[it's]' || Q'{a}' || nq'<b>' || q'!x!' || 'q''[y]''' ; -- q'[c]'"
    fixed, count = prepare_oracle_alt_quote(source)
    assert count == 4
    assert fixed == "v := 'it''s' || 'a' || N'b' || 'x' || 'q''[y]''' ; -- q'[c]'"


def test_brackets_unwrap_plain_names_and_quote_the_rest():
    source = "CREATE TABLE [dbo].[Order Items]([Id] [int], [N]] x] [nvarchar](100)); SELECT '[a]' -- [b]"
    fixed, count = prepare_mssql_brackets(source)
    assert count == 6
    assert fixed == 'CREATE TABLE dbo."Order Items"(Id int, "N] x" nvarchar(100)); SELECT \'[a]\' -- [b]'


@pytest.mark.parametrize("name", sorted(CASES))
def test_every_rewrite_is_idempotent(name):
    dialect, _, source, *_ = CASES[name]
    once = _prepared(dialect, source)
    assert _prepared(dialect, once) == once


def test_every_preparer_names_a_real_gap():
    from ora2pg_gap_report.gap_registry import gap_by_detector

    for preparers in PREPARERS_BY_DIALECT.values():
        for preparer in preparers:
            assert gap_by_detector(PREPARER_DETECTOR[preparer]) is not None


def test_cli_prepare_dry_run_and_write(tmp_path, capsys):
    dump = tmp_path / "dump.sql"
    dump.write_bytes(CASES["g087_brackets"][2].replace("\n", "\r\n").encode())
    assert main(["--lang", "en", "--prepare", "--dialect", "mssql", str(dump)]) == 0
    assert b"[dbo]" in dump.read_bytes(), "dry run must not touch the file"
    assert "+CREATE TABLE dbo.Orders(" in capsys.readouterr().out
    assert main(["--lang", "en", "--prepare", "--dialect", "mssql", "--write", str(dump)]) == 0
    written = dump.read_bytes()
    assert b"CREATE TABLE dbo.Orders(\r\n" in written  # line endings kept


def test_cli_prepare_and_fix_cannot_be_combined(tmp_path, capsys):
    dump = tmp_path / "dump.sql"
    dump.write_text("SELECT 1;\n", encoding="utf-8")
    assert main(["--lang", "en", "--prepare", "--fix", str(dump)]) == 2
    assert "different files" in capsys.readouterr().err


# --- the real ora2pg ----------------------------------------------------------


def _ora2pg(tmp_path, dialect, otype, source):
    src = tmp_path / "in.sql"
    src.write_text(source, encoding="utf-8")
    flag = {"mysql": ["-m"], "mssql": ["-M"], "oracle": []}[dialect]
    subprocess.run(
        ["ora2pg", *flag, "-t", otype, "-i", str(src), "-o", "out.sql", "-b", str(tmp_path)],
        capture_output=True,
        timeout=120,
    )
    out = tmp_path / "out.sql"
    return out.read_text(encoding="utf-8") if out.exists() else ""


@pytest.mark.ora2pg
@pytest.mark.skipif(shutil.which("ora2pg") is None, reason="no ora2pg on PATH")
@pytest.mark.parametrize("name", sorted(CASES))
def test_real_ora2pg_mangles_the_original_and_converts_the_prepared(name, tmp_path):
    dialect, otype, source, expected, *_ = CASES[name]
    broken_sign = BROKEN_SIGN.get(name)
    (tmp_path / "original").mkdir()
    (tmp_path / "prepared").mkdir()
    original = _ora2pg(tmp_path / "original", dialect, otype, source)
    prepared = _ora2pg(tmp_path / "prepared", dialect, otype, _prepared(dialect, source))
    assert expected in prepared
    # If these fail, ora2pg handles the original itself now: the gap and
    # its rewrite should be re-examined, not the assertion loosened.
    if broken_sign is None:
        assert expected not in original
    else:
        assert broken_sign in original and broken_sign not in prepared


# --- the result in PostgreSQL ------------------------------------------------


def _docker_usable():
    if not sys.platform.startswith("linux") or shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@pytest.mark.docker
@pytest.mark.skipif(not _docker_usable(), reason="needs a working docker (Linux)")
@pytest.mark.parametrize("name", sorted(CASES))
def test_ora2pgs_output_for_the_prepared_source_loads_and_works(name, tmp_path):
    from ora2pg_gap_report.load_check import parse_target, run_load_check

    dialect, _, _, _, setup, check = CASES[name]
    first = tmp_path / "0_setup.sql"
    first.write_text(setup + "\n", encoding="utf-8")
    generated = tmp_path / "1_generated.sql"
    generated.write_text((FIXTURES / f"{name}.sql").read_text(encoding="utf-8") + "\n" + check + "\n", encoding="utf-8")
    result = run_load_check([first, generated], parse_target("docker"), dialect=dialect)
    assert result.errors == (), [(e.line, e.sqlstate, e.message) for e in result.errors]
