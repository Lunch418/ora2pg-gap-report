from ora2pg_gap_report.detectors.json_table import find_json_table_calls


def test_json_table_call_is_flagged():
    source = (
        "create or replace procedure parse_orders as\n"
        "  v_count number;\n"
        "begin\n"
        "  select count(*) into v_count\n"
        "  from json_table(v_json, '$[*]' columns (id number path '$.id'));\n"
        "end;\n"
        "/\n"
    )
    findings = find_json_table_calls(source)
    assert len(findings) == 1
    assert findings[0].object_name == "PARSE_ORDERS"
    assert findings[0].snippet == "JSON_TABLE(...)"
    assert findings[0].severity == "high"


def test_unrelated_call_is_not_flagged():
    source = "select json_value(v_json, '$.id') from dual;\n"
    assert find_json_table_calls(source) == []
