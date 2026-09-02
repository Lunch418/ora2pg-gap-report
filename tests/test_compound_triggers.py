from pathlib import Path

from ora2pg_gap_report.detectors.compound_triggers import find_compound_triggers

SAMPLES = Path(__file__).resolve().parents[1] / "docs" / "research" / "samples"


def test_detects_compound_trigger_in_apress_sample():
    source = (SAMPLES / "compound_trigger_apress.sql").read_text(encoding="utf-8")
    findings = find_compound_triggers(source)

    assert {f.object_name for f in findings} == {"TR_CONSTRUCTORS_CTI"}
    assert findings[0].severity == "high"
    assert findings[0].detector == "compound_triggers"


def test_dlee_sample_flags_only_the_compound_trigger_not_the_plain_ones():
    # Real file with 4 ordinary triggers (equitable_salaries_bstrg/rtrg/astrg
    # and an earlier equitable_salary_trg) plus one COMPOUND TRIGGER variant
    # of the same logic later in the file, plus an anonymous PL/SQL block —
    # a good real-world test that trigger boundaries aren't confused by
    # any of that.
    source = (SAMPLES / "compound_trigger_dlee.sql").read_text(encoding="utf-8")
    findings = find_compound_triggers(source)

    assert len(findings) == 1
    assert findings[0].object_name == "EQUITABLE_SALARY_TRG"


def test_no_false_positive_on_ordinary_trigger():
    source = """
    create or replace trigger trg_audit
      before insert or update on employees
      for each row
    begin
      :new.updated_at := sysdate;
    end trg_audit;
    /
    """
    assert find_compound_triggers(source) == []


def test_ignores_compound_trigger_mentioned_only_in_a_comment_or_string():
    source = """
    create or replace trigger trg_audit
      -- note: this is NOT a compound trigger, just a plain one
      before insert on employees
    begin
      v_note varchar2(40) := 'compound trigger style not used here';
      null;
    end trg_audit;
    /
    """
    assert find_compound_triggers(source) == []


def test_multiple_plain_triggers_in_one_file_none_flagged():
    source = """
    create or replace trigger t1 before insert on a begin null; end t1;
    /
    create or replace trigger t2 before update on b begin null; end t2;
    /
    """
    assert find_compound_triggers(source) == []
