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


def test_json_table_as_a_suffix_of_a_longer_identifier_is_not_flagged():
    # The word boundary in \bJSON_TABLE\s*\( means an identifier merely
    # ending in "json_table" (e.g. a helper function someone happened to
    # name my_json_table) must not match -- there's no real boundary
    # between "my_" and "json_table" for regex purposes (underscore is a
    # word character), so this is also a check that the regex doesn't
    # accidentally match mid-identifier despite \b.
    source = "select my_json_table(v_json) from dual;\n"
    assert find_json_table_calls(source) == []


def test_json_table_without_a_following_paren_is_not_flagged():
    # JSON_TABLE used as a plain identifier (e.g. a column or alias named
    # after the function, with no call parens) is not a real invocation.
    source = "select json_table from some_metadata_view;\n"
    assert find_json_table_calls(source) == []


def test_json_table_is_case_insensitive():
    source = "select * from Json_Table(v_json, '$' columns (id number path '$.id'));\n"
    assert len(find_json_table_calls(source)) == 1
