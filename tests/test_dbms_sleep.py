from pathlib import Path

from ora2pg_gap_report.autofix import fix_bare_pg_sleep
from ora2pg_gap_report.detectors.dbms_sleep import find_dbms_sleep

FIXTURES = Path(__file__).parent / "fixtures" / "gaps_120_123"


def test_sleep_calls_are_flagged():
    found = find_dbms_sleep((FIXTURES / "edge_source.sql").read_text(encoding="utf-8"))
    assert [(f.line, f.snippet) for f in found] == [
        (17, "DBMS_SESSION.SLEEP"),  # SYS.-qualified
        (18, "DBMS_SESSION.SLEEP"),  # after THEN
        (30, "DBMS_SESSION.SLEEP"),  # in a trigger
    ]


def test_other_mentions_are_not_flagged():
    source = "BEGIN\n  -- DBMS_LOCK.SLEEP(1);\n  x := 'DBMS_LOCK.SLEEP(1);';\n  my_pkg.sleep(1);\nEND;\n"
    assert find_dbms_sleep(source) == []


def test_fix_writes_perform_on_real_output():
    for name in ("edge_PACKAGE_output.sql", "edge_TRIGGER_output.sql"):
        output = (FIXTURES / name).read_text(encoding="utf-8")
        fixed, count = fix_bare_pg_sleep(output)
        assert count == output.count("pg_sleep(") > 0
        assert fixed.count("PERFORM pg_sleep(") == count
        assert fix_bare_pg_sleep(fixed) == (fixed, 0)


def test_fix_leaves_select_strings_and_performs_alone():
    text = "BEGIN\n  PERFORM pg_sleep(1);\n  SELECT pg_sleep(2);\n  RAISE NOTICE 'x; pg_sleep(3)';\n  v := pg_sleep(4);\n"
    assert fix_bare_pg_sleep(text) == (text, 0)
