from ora2pg_gap_report.detectors.for_update_wait import find_for_update_wait


def test_for_update_of_with_a_wait_timeout_is_flagged():
    source = "SELECT * FROM accounts WHERE id = 1 FOR UPDATE OF bal WAIT 5;\n"
    findings = find_for_update_wait(source)
    assert len(findings) == 1
    assert findings[0].snippet == "FOR UPDATE OF bal WAIT 5".upper()
    assert findings[0].severity == "high"


def test_for_update_without_the_of_list_is_flagged():
    assert len(find_for_update_wait("SELECT * FROM t FOR UPDATE WAIT 10;\n")) == 1


def test_nowait_is_not_flagged():
    # PostgreSQL spells NOWAIT the same way and ora2pg carries it across
    # correctly -- only the numeric-timeout form is a gap.
    assert find_for_update_wait("SELECT * FROM t FOR UPDATE NOWAIT;\n") == []


def test_skip_locked_is_not_flagged():
    assert find_for_update_wait("SELECT * FROM t FOR UPDATE SKIP LOCKED;\n") == []


def test_a_plain_for_update_is_not_flagged():
    assert find_for_update_wait("SELECT * FROM t FOR UPDATE;\n") == []


def test_a_column_named_wait_is_not_flagged():
    assert find_for_update_wait("SELECT wait FROM queue_config;\n") == []
