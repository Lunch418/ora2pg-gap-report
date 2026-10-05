from ora2pg_gap_report.detectors.repeated_package_call import find_repeated_package_call

HEAD = """CREATE OR REPLACE PACKAGE BODY job_pkg AS
  PROCEDURE refresh IS
  BEGIN
    NULL;
  END;
  PROCEDURE log_it(p VARCHAR2) IS
  BEGIN
    NULL;
  END;
"""


def _body(calls):
    return HEAD + "  PROCEDURE run_all IS\n  BEGIN\n" + "".join(f"    {c}\n" for c in calls) + "  END;\nEND job_pkg;\n/\n"


def test_a_qualified_repeat_without_parentheses_is_flagged():
    # The shapes ora2pg 25.0 left without CALL.
    for calls in (["refresh;", "job_pkg.refresh;"], ["job_pkg.refresh;", "job_pkg.refresh;"]):
        findings = find_repeated_package_call(_body(calls))
        assert [(f.object_name, f.line, f.snippet) for f in findings] == [
            ("JOB_PKG.RUN_ALL", 13, "job_pkg.refresh;")
        ], calls


def test_the_shapes_ora2pg_converts_are_not_flagged():
    for calls in (
        ["job_pkg.refresh;"],                         # once
        ["refresh;", "refresh;"],                     # unqualified repeat
        ["job_pkg.refresh();", "job_pkg.refresh();"],  # with parentheses
        ["job_pkg.log_it('a');", "job_pkg.log_it('b');"],  # with arguments
        ["other_pkg.refresh;", "other_pkg.refresh;"],  # not this package
    ):
        assert find_repeated_package_call(_body(calls)) == [], calls


def test_calls_in_different_routines_do_not_add_up():
    source = HEAD + (
        "  PROCEDURE a IS\n  BEGIN\n    job_pkg.refresh;\n  END;\n"
        "  PROCEDURE b IS\n  BEGIN\n    job_pkg.refresh;\n  END;\n"
        "END job_pkg;\n/\n"
    )
    assert find_repeated_package_call(source) == []
