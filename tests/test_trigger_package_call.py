from ora2pg_gap_report.detectors.trigger_package_call import find_trigger_package_call

TRIGGER = """CREATE OR REPLACE TRIGGER t_biu BEFORE INSERT OR UPDATE ON orders FOR EACH ROW
DECLARE
  v NUMBER;
BEGIN
  audit_pkg.log_change(:NEW.id, 'X');
  audit_pkg.touch;
  v := audit_pkg.next_seq(:NEW.id);
  :NEW.total := v;
  dbms_output.put_line('done');
  IF v > 0 THEN
    stats_pkg.bump(1);
  END IF;
END;
/
"""


def test_package_procedure_calls_in_a_trigger_are_flagged():
    findings = find_trigger_package_call(TRIGGER)
    assert [(f.object_name, f.line, f.snippet) for f in findings] == [
        ("T_BIU", 5, "audit_pkg.log_change"),
        ("T_BIU", 6, "audit_pkg.touch"),
        ("T_BIU", 11, "stats_pkg.bump"),
    ]


def test_function_calls_pseudo_records_and_builtins_are_not():
    source = TRIGGER.replace("  audit_pkg.log_change(:NEW.id, 'X');\n  audit_pkg.touch;\n", "").replace(
        "    stats_pkg.bump(1);\n", "    NULL;\n"
    )
    assert find_trigger_package_call(source) == []


def test_calls_in_a_package_are_not_this_gap():
    source = "CREATE OR REPLACE PACKAGE BODY p AS\n  PROCEDURE x IS\n  BEGIN\n    other_pkg.go;\n  END;\nEND p;\n/\n"
    assert find_trigger_package_call(source) == []


def test_the_real_compound_trigger_sample():
    # Where --load-check first showed it: the trigger calls its package.
    from pathlib import Path

    sample = Path(__file__).parents[1] / "docs" / "research" / "samples" / "compound_trigger_dlee.sql"
    snippets = {f.snippet.lower() for f in find_trigger_package_call(sample.read_text(encoding="utf-8"))}
    assert "equitable_salaries_pkg.make_equitable" in snippets
