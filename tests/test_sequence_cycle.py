from ora2pg_gap_report.detectors.sequence_cycle import find_sequence_cycle_usage


def test_cycle_sequence_is_flagged():
    source = "create sequence seq_small increment by 1 maxvalue 3 cycle;\n"
    findings = find_sequence_cycle_usage(source)
    assert len(findings) == 1
    assert findings[0].object_name == "SEQ_SMALL"
    assert findings[0].severity == "high"


def test_nocycle_sequence_is_not_flagged():
    source = "create sequence seq_small increment by 1 maxvalue 3 nocycle;\n"
    assert find_sequence_cycle_usage(source) == []


def test_plain_sequence_without_cycle_or_nocycle_is_not_flagged():
    source = "create sequence seq_plain increment by 1;\n"
    assert find_sequence_cycle_usage(source) == []


def test_cycle_is_not_misattributed_to_a_later_unrelated_sequence():
    source = (
        "create sequence seq_a maxvalue 3 cycle;\n"
        "create sequence seq_b increment by 1;\n"
    )
    findings = find_sequence_cycle_usage(source)
    assert len(findings) == 1
    assert findings[0].object_name == "SEQ_A"


def test_unterminated_statement_does_not_bleed_into_an_earlier_sequence():
    source = (
        "create sequence seq_plain increment by 1\n"
        "create sequence seq_small maxvalue 3 cycle\n"
    )
    findings = find_sequence_cycle_usage(source)
    assert len(findings) == 1
    assert findings[0].object_name == "SEQ_SMALL"


def test_reported_line_is_the_cycle_token_not_the_create_sequence_line():
    source = (
        "create sequence seq_small\n"
        "  increment by 1\n"
        "  maxvalue 3\n"
        "  cycle;\n"
    )
    findings = find_sequence_cycle_usage(source)
    assert len(findings) == 1
    assert findings[0].line == 4
