from ora2pg_gap_report.detectors.mssql_update_set import find_mssql_update_set


def test_an_update_set_is_flagged():
    source = (
        "CREATE PROCEDURE dbo.upd @x int AS\n"
        "BEGIN\n"
        "    UPDATE orders SET amount = @x, nm = 'y' WHERE id = 1;\n"
        "END;\n"
    )
    findings = find_mssql_update_set(source)
    assert len(findings) == 1
    assert findings[0].object_name == "UPD"
    assert findings[0].snippet == "UPDATE ... SET"
    assert findings[0].severity == "high"
    assert findings[0].line == 3

def test_a_bracket_quoted_target_is_flagged():
    source = "CREATE PROCEDURE dbo.p AS\nBEGIN\n  UPDATE [dbo].[Orders] SET [Note] = 'x';\nEND;\n"
    assert len(find_mssql_update_set(source)) == 1


def test_two_updates_are_both_flagged():
    source = (
        "CREATE PROCEDURE dbo.p AS\n"
        "BEGIN\n"
        "  UPDATE a SET x = 1;\n"
        "  UPDATE b SET y = 2;\n"
        "END;\n"
    )
    assert len(find_mssql_update_set(source)) == 2


def test_the_construct_inside_a_string_literal_is_not_flagged():
    source = "CREATE PROCEDURE dbo.p AS BEGIN SELECT 'UPDATE t SET a = 1'; END;\n"
    assert find_mssql_update_set(source) == []

def test_a_tsql_variable_assignment_is_not_flagged():
    # SET @x = 1 is the assignment ora2pg handles correctly -- the bug is that
    # it applies those rules to an UPDATE as well.
    assert find_mssql_update_set('CREATE PROCEDURE dbo.p @x int AS BEGIN SET @x = 1; END;\n') == []

def test_a_select_is_not_flagged():
    # No UPDATE at all.
    assert find_mssql_update_set('CREATE PROCEDURE dbo.p AS BEGIN SELECT a FROM t; END;\n') == []
