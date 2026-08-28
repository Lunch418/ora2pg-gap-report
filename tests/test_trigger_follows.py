from ora2pg_gap_report.detectors.trigger_follows import find_trigger_follows


def test_a_follows_clause_in_the_trigger_header_is_flagged():
    source = (
        "CREATE OR REPLACE TRIGGER trg_b\n"
        "BEFORE INSERT ON employees\n"
        "FOR EACH ROW\n"
        "FOLLOWS trg_a\n"
        "BEGIN\n"
        "  :NEW.audited := 'Y';\n"
        "END;\n"
    )
    findings = find_trigger_follows(source)
    assert len(findings) == 1
    assert findings[0].object_name == "TRG_B"
    assert findings[0].snippet == "FOLLOWS TRG_A"
    assert findings[0].severity == "high"
    assert findings[0].line == 4


def test_precedes_is_flagged_too():
    source = (
        "CREATE TRIGGER t\nBEFORE INSERT ON e FOR EACH ROW\nPRECEDES other_trg\nBEGIN\n NULL;\nEND;\n"
    )
    findings = find_trigger_follows(source)
    assert len(findings) == 1
    assert findings[0].snippet == "PRECEDES OTHER_TRG"


def test_a_schema_qualified_predecessor_name_is_captured():
    source = "CREATE TRIGGER t\nBEFORE INSERT ON e FOR EACH ROW\nFOLLOWS hr.trg_a\nBEGIN\n NULL;\nEND;\n"
    assert find_trigger_follows(source)[0].snippet == "FOLLOWS HR.TRG_A"


def test_follows_used_as_an_ordinary_identifier_is_not_flagged():
    # The whole reason the detector is scoped to the trigger header:
    # FOLLOWS is a perfectly legal column name.
    assert find_trigger_follows("SELECT follows FROM social;\n") == []


def test_follows_inside_a_trigger_body_is_not_flagged():
    source = (
        "CREATE TRIGGER t\n"
        "BEFORE INSERT ON e FOR EACH ROW\n"
        "BEGIN\n"
        "  SELECT follows count INTO n FROM social;\n"
        "END;\n"
    )
    assert find_trigger_follows(source) == []


def test_an_ordinary_trigger_is_not_flagged():
    source = "CREATE TRIGGER t\nBEFORE INSERT ON e FOR EACH ROW\nBEGIN\n NULL;\nEND;\n"
    assert find_trigger_follows(source) == []
