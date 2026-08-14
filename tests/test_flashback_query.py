from ora2pg_gap_report.detectors.flashback_query import find_flashback_queries


def test_as_of_timestamp_is_flagged_inside_a_package_body():
    source = """
    create or replace package body audit_pkg as
      procedure compare_state is
        v_count number;
      begin
        select count(*) into v_count
        from orders as of timestamp (systimestamp - interval '1' day)
        where status = 'OPEN';
      end compare_state;
    end audit_pkg;
    /
    """
    findings = find_flashback_queries(source)
    assert len(findings) == 1
    assert findings[0].object_name == "AUDIT_PKG.COMPARE_STATE"
    assert findings[0].snippet.lower() == "as of timestamp"
    assert findings[0].severity == "high"


def test_as_of_scn_is_also_flagged():
    source = """
    create or replace procedure noop as
    begin
      insert into t select * from orders as of scn 123456;
    end noop;
    /
    """
    findings = find_flashback_queries(source)
    assert len(findings) == 1
    assert findings[0].snippet.lower() == "as of scn"


def test_ordinary_procedure_without_flashback_is_not_flagged():
    source = """
    create or replace package body plain_pkg as
      procedure noop is
      begin
        null;
      end noop;
    end plain_pkg;
    /
    """
    assert find_flashback_queries(source) == []


def test_snippet_whitespace_is_normalized_for_a_line_wrapped_match():
    # A newline embedded in the snippet would break out of a markdown
    # table cell in --format markdown output.
    source = """
    create or replace procedure noop as
    begin
      select 1 from orders as of
        timestamp (sysdate - 1);
    end noop;
    /
    """
    findings = find_flashback_queries(source)
    assert len(findings) == 1
    assert "\n" not in findings[0].snippet
    assert findings[0].snippet.lower() == "as of timestamp"
