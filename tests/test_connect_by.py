from pathlib import Path

from src.detectors.connect_by import find_connect_by_risks, has_connect_by

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAMPLES = Path(__file__).resolve().parents[1] / "docs" / "research" / "samples"


def test_has_connect_by_true_on_the_connect_by_fixture():
    source = (SAMPLES / "connect_by_hierarchy_pkg.sql").read_text()
    assert has_connect_by(source) is True


def test_has_connect_by_false_on_a_package_without_it():
    source = (SAMPLES / "sql_util_pkg.pkb").read_text()
    assert has_connect_by(source) is False


def test_finds_the_real_level_alias_bug_in_generated_output():
    # Fixture captured from a real run:
    # ora2pg -t PACKAGE -i connect_by_hierarchy_pkg.sql --estimate_cost
    output = (FIXTURES / "ora2pg_generated_connect_by_hierarchy.sql").read_text()
    findings = find_connect_by_risks(output)

    assert len(findings) == 1
    f = findings[0]
    assert f.detector == "connect_by"
    assert f.object_name == "CTE"
    assert f.severity == "high"
    assert f.snippet.lower() == "c.level"


def test_no_false_positive_on_a_correctly_generated_with_recursive():
    # A hand-written "what it should have looked like" — the anchor branch
    # names its counter column, and the recursive branch consistently uses
    # that name instead of the leftover Oracle keyword LEVEL.
    output = """
    CREATE OR REPLACE FUNCTION get_org_chart(p_top_id bigint) RETURNS refcursor AS $body$
    BEGIN
      OPEN l_cursor FOR
        WITH RECURSIVE cte AS (
          SELECT employee_id, manager_id, 1 AS depth
          FROM employees WHERE employee_id = p_top_id
        UNION ALL
          SELECT e.employee_id, e.manager_id, c.depth + 1
          FROM employees e JOIN cte c ON (c.employee_id = e.manager_id)
        ) SELECT * FROM cte;
      RETURN l_cursor;
    END;
    $body$ LANGUAGE PLPGSQL;
    """
    assert find_connect_by_risks(output) == []


def test_no_false_positive_when_output_has_no_with_recursive_at_all():
    output = "CREATE OR REPLACE FUNCTION foo() RETURNS int AS $$ BEGIN RETURN 1; END; $$ LANGUAGE plpgsql;"
    assert find_connect_by_risks(output) == []


def test_level_reference_outside_a_with_recursive_block_is_not_flagged():
    # A column or variable literally named "level" elsewhere in the file
    # (unrelated to CONNECT BY conversion) must not trigger this linter —
    # only LEVEL inside a WITH RECURSIVE's own body is the actual bug.
    output = """
    CREATE OR REPLACE FUNCTION set_level(p_level int) RETURNS void AS $$
    BEGIN
      UPDATE settings SET level = p_level;
    END;
    $$ LANGUAGE plpgsql;
    """
    assert find_connect_by_risks(output) == []
