"""CLI behaviour of --verify/--fix/--check-connect-by across dialects.

The scan side of --dialect is covered by each detector's own tests; what
matters here is the machinery that has to agree about a dialect *between*
runs -- a snapshot written by one scan and verified after a real
migration -- plus the guards that refuse a combination rather than
producing a confidently wrong answer.
"""

import json

from ora2pg_gap_report.cli import main

# The MySQL construct here is GAP-070 (ON DUPLICATE KEY UPDATE), which
# ora2pg copies verbatim into its output -- the VERBATIM classification
# that makes re-detection meaningful in the first place.
_MYSQL_SOURCE = """CREATE TABLE counters (id INT PRIMARY KEY, hits INT NOT NULL DEFAULT 0);
CREATE PROCEDURE bump(IN p_id INT)
BEGIN
  INSERT INTO counters (id, hits) VALUES (p_id, 1)
    ON DUPLICATE KEY UPDATE hits = hits + 1;
END;
"""

# What ora2pg -m actually emits for it: the clause carried through into a
# PL/pgSQL body (abridged from a real run).
_MYSQL_GENERATED_STILL_BROKEN = """CREATE OR REPLACE PROCEDURE bump (IN p_id integer) AS $body$
BEGIN
  INSERT INTO counters(id, hits) VALUES (p_id, 1)
    ON DUPLICATE KEY UPDATE hits = hits + 1;
END;
$body$
LANGUAGE PLPGSQL;
"""

_MYSQL_GENERATED_FIXED = """CREATE OR REPLACE PROCEDURE bump (IN p_id integer) AS $body$
BEGIN
  INSERT INTO counters(id, hits) VALUES (p_id, 1)
    ON CONFLICT (id) DO UPDATE SET hits = counters.hits + 1;
END;
$body$
LANGUAGE PLPGSQL;
"""


def _save_mysql_baseline(tmp_path):
    source = tmp_path / "schema.sql"
    source.write_text(_MYSQL_SOURCE, encoding="utf-8")
    baseline = tmp_path / "base.json"
    assert main(["--dialect", "mysql", str(source), "--save", str(baseline), "--format", "json"]) == 0
    return baseline


def test_a_mysql_baseline_records_mysql_detectors(tmp_path):
    baseline = _save_mysql_baseline(tmp_path)
    saved = json.loads(baseline.read_text(encoding="utf-8"))
    detectors = {f["detector"] for f in saved["findings"]}
    assert detectors == {"mysql_on_duplicate_key_update"}


def test_verify_infers_the_dialect_from_the_baseline_without_the_flag(tmp_path, capsys):
    # The point of inferring: the user does not have to remember which
    # dialect the snapshot was taken with, and cannot get it wrong.
    baseline = _save_mysql_baseline(tmp_path)
    generated = tmp_path / "generated.sql"
    generated.write_text(_MYSQL_GENERATED_STILL_BROKEN, encoding="utf-8")

    exit_code = main(["--verify", "--baseline", str(baseline), str(generated)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "STILL_PRESENT" in captured.out
    assert "mysql_on_duplicate_key_update" in captured.out


def test_verify_reports_not_detected_once_the_construct_is_rewritten(tmp_path, capsys):
    baseline = _save_mysql_baseline(tmp_path)
    generated = tmp_path / "generated.sql"
    generated.write_text(_MYSQL_GENERATED_FIXED, encoding="utf-8")

    exit_code = main(["--verify", "--baseline", str(baseline), str(generated)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "NOT_DETECTED" in captured.out
    assert "STILL_PRESENT" not in captured.out


def test_verify_accepts_an_explicit_dialect_that_matches_the_baseline(tmp_path, capsys):
    baseline = _save_mysql_baseline(tmp_path)
    generated = tmp_path / "generated.sql"
    generated.write_text(_MYSQL_GENERATED_STILL_BROKEN, encoding="utf-8")

    exit_code = main(["--verify", "--dialect", "mysql", "--baseline", str(baseline), str(generated)])
    assert exit_code == 0
    assert "STILL_PRESENT" in capsys.readouterr().out


def test_verify_rejects_an_explicit_dialect_that_contradicts_the_baseline(tmp_path, capsys):
    # Scanning MySQL findings with MSSQL detectors would report
    # "not detected" for every one of them -- a tautology, not a check.
    baseline = _save_mysql_baseline(tmp_path)
    generated = tmp_path / "generated.sql"
    generated.write_text(_MYSQL_GENERATED_STILL_BROKEN, encoding="utf-8")

    exit_code = main(["--verify", "--dialect", "mssql", "--baseline", str(baseline), str(generated)])
    assert exit_code == 2
    assert "mysql" in capsys.readouterr().err


def test_verify_rejects_a_baseline_mixing_dialects(tmp_path, capsys):
    baseline = tmp_path / "mixed.json"
    baseline.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "findings": [
                    {"group_key": "a", "detector": "mysql_signal"},
                    {"group_key": "b", "detector": "bulk_collect"},
                ],
            }
        )
    , encoding="utf-8")
    generated = tmp_path / "generated.sql"
    generated.write_text("SELECT 1;\n", encoding="utf-8")

    assert main(["--verify", "--baseline", str(baseline), str(generated)]) == 2
    err = capsys.readouterr().err
    assert "mysql" in err and "oracle" in err


def test_verify_rejects_a_baseline_naming_detectors_this_build_lacks(tmp_path, capsys):
    baseline = tmp_path / "future.json"
    baseline.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "findings": [{"group_key": "a", "detector": "detector_from_the_future"}],
            }
        )
    , encoding="utf-8")
    generated = tmp_path / "generated.sql"
    generated.write_text("SELECT 1;\n", encoding="utf-8")

    assert main(["--verify", "--baseline", str(baseline), str(generated)]) == 2
    assert "detector_from_the_future" in capsys.readouterr().err


def test_an_oracle_baseline_still_verifies_exactly_as_before(tmp_path, capsys):
    # Regression guard for the whole inference change: an Oracle snapshot
    # must keep working with no flag and no schema change.
    source = tmp_path / "src.sql"
    source.write_text("SELECT * FROM t CROSS APPLY (SELECT 1) x;\n", encoding="utf-8")
    baseline = tmp_path / "base.json"
    assert main([str(source), "--save", str(baseline), "--format", "json"]) == 0

    generated = tmp_path / "generated.sql"
    generated.write_text("SELECT * FROM t CROSS APPLY (SELECT 1) x;\n", encoding="utf-8")
    assert main(["--verify", "--baseline", str(baseline), str(generated)]) == 0
    assert "STILL_PRESENT" in capsys.readouterr().out


# --- --fix -----------------------------------------------------------------

_MSSQL_GENERATED_BROKEN = """SET check_function_bodies = false;

CREATE OR REPLACE PROCEDURE dbo.clean_np () AS $body$
DECLARE

;
BEGIN
  SELECT position(''abc'' in nm);
END;
$body$
LANGUAGE PLPGSQL;
"""


def test_fix_applies_every_mssql_fixer_in_one_pass(tmp_path, capsys):
    generated = tmp_path / "generated.sql"
    generated.write_text(_MSSQL_GENERATED_BROKEN, encoding="utf-8")

    exit_code = main(["--fix", "--write", "--dialect", "mssql", str(generated)])
    assert exit_code == 0
    fixed = generated.read_text(encoding="utf-8")
    assert "DECLARE" not in fixed
    assert "position('abc' in nm)" in fixed


def test_fix_is_a_dry_run_without_write(tmp_path, capsys):
    generated = tmp_path / "generated.sql"
    generated.write_text(_MSSQL_GENERATED_BROKEN, encoding="utf-8")

    assert main(["--fix", "--dialect", "mssql", str(generated)]) == 0
    assert generated.read_text(encoding="utf-8") == _MSSQL_GENERATED_BROKEN, "dry run must not touch the file"
    assert "-DECLARE" in capsys.readouterr().out


def test_fix_says_so_when_a_dialect_has_no_mechanical_fixes(tmp_path, capsys):
    # Reporting "nothing to fix" per file would read as "your output is
    # fine", which is a different and wrong claim.
    generated = tmp_path / "generated.sql"
    generated.write_text(_MSSQL_GENERATED_BROKEN, encoding="utf-8")

    assert main(["--fix", "--dialect", "mysql", str(generated)]) == 2
    assert "mysql" in capsys.readouterr().err


def test_fix_still_defaults_to_the_oracle_fixer(tmp_path, capsys):
    generated = tmp_path / "generated.sql"
    generated.write_text("CREATE TABLE t (id bigint GENERATED ALWAYS AS IDENTITY ((START WITH 1)));\n", encoding="utf-8")

    assert main(["--fix", "--write", str(generated)]) == 0
    assert "IDENTITY (START WITH 1)" in generated.read_text(encoding="utf-8")


# --- --check-connect-by ----------------------------------------------------


def test_check_connect_by_is_rejected_for_a_non_oracle_dialect(tmp_path, capsys):
    # The check runs ora2pg in Oracle mode and looks for Oracle-only
    # syntax; accepting it elsewhere would be a silent no-op.
    source = tmp_path / "schema.sql"
    source.write_text(_MYSQL_SOURCE, encoding="utf-8")

    assert main(["--dialect", "mysql", "--check-connect-by", str(source)]) == 2
    assert "mysql" in capsys.readouterr().err
