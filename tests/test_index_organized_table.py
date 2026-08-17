from ora2pg_gap_report.detectors.index_organized_table import find_index_organized_tables


def test_organization_index_is_flagged():
    source = (
        "create table lookup_cache (\n"
        "  cache_key varchar2(64),\n"
        "  cache_value varchar2(4000),\n"
        "  constraint pk_lookup_cache primary key (cache_key)\n"
        ") organization index;\n"
    )
    findings = find_index_organized_tables(source)
    assert len(findings) == 1
    assert findings[0].object_name == "LOOKUP_CACHE"
    assert findings[0].severity == "medium"


def test_ordinary_heap_table_is_not_flagged():
    source = "create table orders (order_id number primary key);\n"
    assert find_index_organized_tables(source) == []


def test_organization_external_is_not_confused_with_organization_index():
    # GAP-018's own territory ('CREATE TABLE ... ORGANIZATION EXTERNAL')
    # -- a different clause entirely, must not match here.
    source = "create table ext_orders (order_id number) organization external (default directory ext_dir);\n"
    assert find_index_organized_tables(source) == []


def test_organization_index_is_not_misattributed_to_a_later_unrelated_table():
    source = (
        "create table iot_a (id number primary key) organization index;\n"
        "create table heap_b (id number);\n"
    )
    findings = find_index_organized_tables(source)
    assert len(findings) == 1
    assert findings[0].object_name == "IOT_A"


def test_unterminated_statement_does_not_bleed_into_an_earlier_table():
    source = (
        "create table small_lookup (id number)\n"
        "create table lookup_cache (cache_key varchar2(64) primary key) organization index\n"
    )
    findings = find_index_organized_tables(source)
    assert len(findings) == 1
    assert findings[0].object_name == "LOOKUP_CACHE"


def test_double_quoted_column_named_organization_index_is_not_a_false_positive():
    # mask_strings_and_comments() only masks single-quoted string
    # literals/comments, never double-quoted identifiers -- a column
    # named "ORGANIZATION INDEX" (valid Oracle identifier syntax) must
    # not be confused with the real trailing clause.
    source = 'create table t (id number, "ORGANIZATION INDEX" varchar2(10));\n'
    assert find_index_organized_tables(source) == []


def test_reported_line_is_the_organization_index_token_not_the_create_table_line():
    source = (
        "create table lookup_cache (\n"
        "  cache_key varchar2(64) primary key\n"
        ")\n"
        "organization index;\n"
    )
    findings = find_index_organized_tables(source)
    assert len(findings) == 1
    assert findings[0].line == 4
