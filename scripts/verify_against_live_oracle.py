#!/usr/bin/env python3
"""Live verification against a real Oracle instance — the one part of
this project that unit tests with a fake connection (tests/fakes/
fake_oracle.py) can't cover on their own.

Requires ORACLE_DSN / ORACLE_USER / ORACLE_PASSWORD env vars pointing at a
running Oracle instance — scripts/oracle-test-compose.yml spins one up
with `docker compose -f scripts/oracle-test-compose.yml up -d` — and
python-oracledb installed (`pip install -e ".[oracle]"` from a checkout).

    docker compose -f scripts/oracle-test-compose.yml up -d
    docker compose -f scripts/oracle-test-compose.yml logs -f   # wait for "DATABASE IS READY TO USE"
    ORACLE_DSN=localhost:1521/FREEPDB1 ORACLE_USER=testuser ORACLE_PASSWORD=testpass1 \\
      python scripts/verify_against_live_oracle.py

What this does:
  1. Creates a handful of stub tables the trigger fixtures need to exist
     (scripts/setup_oracle_test_schema.sql — CREATE TRIGGER validates its
     target table immediately, unlike packages, which tolerate missing
     dependencies and just compile INVALID).
  2. Loads the real open PL/SQL fixtures from docs/research/samples/ into
     the live schema, unmodified.
  3. Uses oracle_connector.export_schema() — the real, live
     DBMS_METADATA.GET_DDL path — to pull them back out.
  4. Runs this project's own detectors against what came back and checks
     the per-detector totals match what's already verified against these
     same files as plain text (tests/test_autonomous_tx.py etc.).
  5. If a real `ora2pg` binary is on PATH, also runs `ora2pg -t
     SHOW_REPORT` against the live connection — confirming, for the first
     time against an actual Oracle instance rather than by reading source,
     the parts of docs/research/step0-show-report-baseline.md marked "по
     коду, не подтверждено" (most notably: does SHOW_REPORT's live object
     count for COMPOUND TRIGGER look valid the way the research predicted
     from Ora2Pg.pm, since a real Oracle instance wasn't available then
     either).

Individual statement failures while loading fixtures are logged and
skipped rather than aborting the whole run — an INVALID package (missing
table dependency) is expected and fine for this script's purposes; a
genuinely broken run will still show up as a count MISMATCH at the end.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLES = REPO_ROOT / "docs" / "research" / "samples"

sys.path.insert(0, str(REPO_ROOT))
from ora2pg_gap_report import oracle_connector  # noqa: E402
from ora2pg_gap_report.cli import scan_source  # noqa: E402
from ora2pg_gap_report.plsql_lex import mask_strings_and_comments  # noqa: E402


def split_sql_statements(text: str) -> list[str]:
    """SQL*Plus convention: statements separated by a lone '/' on its own
    line (all the CREATE PACKAGE/TRIGGER samples use this). Falls back to
    splitting on ';' for plain DDL scripts that don't (setup_oracle_test_
    schema.sql).

    Splits are located against a comment/string-masked copy of the text
    (same helper the detectors use, for the same reason): a lone '/'
    inside a /* */ comment or a string literal must not be mistaken for a
    statement terminator. A chunk whose *masked* content is entirely
    blank is dropped rather than sent to cursor.execute() — a trailing
    attribution comment block with no code after it is not a statement.
    """
    masked_lines = mask_strings_and_comments(text).splitlines()
    original_lines = text.splitlines()

    if any(line.strip() == "/" for line in masked_lines):
        statements = []
        current_original: list[str] = []
        current_masked: list[str] = []

        def _flush():
            if "".join(current_masked).strip():
                statements.append("\n".join(current_original).strip())

        for masked_line, original_line in zip(masked_lines, original_lines):
            if masked_line.strip() == "/":
                _flush()
                current_original.clear()
                current_masked.clear()
            else:
                current_original.append(original_line)
                current_masked.append(masked_line)
        _flush()
        return statements

    return [s.strip() for s in text.split(";") if s.strip()]


def run_sql_file(conn, path: Path, label: str) -> None:
    statements = split_sql_statements(path.read_text())
    with conn.cursor() as cursor:
        for i, stmt in enumerate(statements, 1):
            try:
                cursor.execute(stmt)
            except Exception as exc:  # noqa: BLE001 — deliberately broad, see module docstring
                print(f"    [{label} #{i}] {type(exc).__name__}: {exc}", file=sys.stderr)
    conn.commit()


def try_live_show_report(dsn: str, user: str, password: str) -> None:
    match = re.match(r"^([^:/]+)(?::(\d+))?/(.+)$", dsn)
    if not match:
        print(f"  не удалось разобрать DSN {dsn!r} в формат ora2pg.conf — пропускаю")
        return
    host, port, service = match.group(1), match.group(2) or "1521", match.group(3)

    with tempfile.TemporaryDirectory() as tmp:
        conf_path = Path(tmp) / "ora2pg.conf"
        conf_path.write_text(
            f"ORACLE_DSN\tdbi:Oracle:host={host};service_name={service};port={port}\n"
            f"ORACLE_USER\t{user}\n"
            f"ORACLE_PWD\t{password}\n"
        )
        try:
            result = subprocess.run(
                ["ora2pg", "-c", str(conf_path), "-t", "SHOW_REPORT"],
                capture_output=True,
                text=True,
                timeout=180,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  ora2pg SHOW_REPORT не удалось запустить: {exc}")
            return
        output = result.stdout or result.stderr
        print("  --- вывод ora2pg SHOW_REPORT (первые 60 строк) ---")
        for line in output.splitlines()[:60]:
            print("  " + line)
        print(
            "  Сверить вручную с предсказанием из docs/research/"
            "step0-show-report-baseline.md раздел 5: компаунд-триггер "
            "должен посчитаться как обычный валидный объект (счётчик "
            "не покажет проблему), в отличие от файлового режима."
        )


def main() -> int:
    dsn = os.environ.get("ORACLE_DSN")
    user = os.environ.get("ORACLE_USER")
    password = os.environ.get("ORACLE_PASSWORD")
    if not (dsn and user and password):
        print("Задайте ORACLE_DSN, ORACLE_USER, ORACLE_PASSWORD.", file=sys.stderr)
        return 2

    print(f"Подключаюсь к {dsn} как {user} ...")
    conn = oracle_connector.connect(dsn, user, password)

    print("Создаю служебные таблицы ...")
    run_sql_file(conn, REPO_ROOT / "scripts" / "setup_oracle_test_schema.sql", "schema")

    print("Загружаю реальные PL/SQL фикстуры ...")
    load_order = [
        "logger.pks",
        "logger.pkb",
        "file_util_pkg.pks",
        "file_util_pkg.pkb",
        "sql_util_pkg.pks",
        "sql_util_pkg.pkb",
        "compound_trigger_apress.sql",
        "compound_trigger_dlee.sql",
        "connect_by_hierarchy_pkg.sql",
    ]
    for name in load_order:
        path = SAMPLES / name
        if not path.exists():
            print(f"  пропуск (не найден): {name}")
            continue
        print(f"  {name}")
        run_sql_file(conn, path, name)

    print("\nВыгружаю живьём через DBMS_METADATA.GET_DDL ...")
    actual_counts: dict[str, int] = {}
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp)
        written = oracle_connector.export_schema(conn, user, output_dir)
        print(f"  выгружено {len(written)} объект(ов): {[p.name for p in written]}")

        print("\nПрогоняю детекторы по живьём выгруженному DDL ...")
        for path in written:
            for f in scan_source(path.read_text()):
                actual_counts[f.detector] = actual_counts.get(f.detector, 0) + 1

    print("\n=== Итог ===")
    ok = True
    # Per-occurrence totals (not unique-object-name counts — those are
    # smaller and are what tests/test_dbms_utl_calls.py asserts, a
    # different thing). Verified directly against the real fixture files:
    # logger.pkb: 17, file_util_pkg.pkb: 40, sql_util_pkg.pkb: 11.
    # compound_triggers: both apress's TR_CONSTRUCTORS_CTI and dlee's
    # EQUITABLE_SALARY_TRG are real, distinctly-named live objects (dlee's
    # earlier same-named plain trigger is DROPped before the COMPOUND
    # TRIGGER version is created) — list_triggers() has no status filter,
    # so both are expected to be exported and detected.
    # bulk_collect: logger.pkb's own 'type ts_array is table of timestamp
    # index by varchar2(100);' (1) plus a local collection TYPE and a
    # FORALL in each of apress's and dlee's compound-trigger fixtures (2
    # each) = 5. merge_delete_clause: 0 — none of these six fixtures use
    # MERGE's DELETE WHERE clause; asserting 0 here still confirms no false
    # positives on a real, varied set of open-source PL/SQL.
    expected_totals = {
        "autonomous_tx": 8,
        "dbms_utl_calls": 17 + 40 + 11,
        "compound_triggers": 2,
        "bulk_collect": 5,
        "merge_delete_clause": 0,
    }
    for detector, expected in expected_totals.items():
        got = actual_counts.get(detector, 0)
        status = "OK" if got == expected else "MISMATCH"
        if got != expected:
            ok = False
        print(f"  {detector}: ожидалось {expected}, получено {got} — {status}")

    if shutil.which("ora2pg"):
        print("\nora2pg найден в PATH — пробую SHOW_REPORT против живого подключения ...")
        try_live_show_report(dsn, user, password)
    else:
        print("\nora2pg не найден в PATH — пропускаю live SHOW_REPORT (см. README).")

    conn.close()
    print("\nОБЩИЙ РЕЗУЛЬТАТ:", "OK" if ok else "MISMATCH — см. вывод выше")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
