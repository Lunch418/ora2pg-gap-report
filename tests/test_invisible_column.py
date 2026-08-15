from ora2pg_gap_report.detectors.invisible_column import find_invisible_columns


def test_invisible_column_is_flagged():
    source = "create table customers (customer_id number, legacy_code varchar2(10) invisible);\n"
    findings = find_invisible_columns(source)
    assert len(findings) == 1
    assert findings[0].object_name == "CUSTOMERS"
    assert findings[0].snippet == "INVISIBLE"
    assert findings[0].severity == "high"


def test_invisible_before_not_null_is_also_flagged():
    source = "create table customers (customer_id number, legacy_code varchar2(10) invisible not null);\n"
    findings = find_invisible_columns(source)
    assert len(findings) == 1


def test_invisible_before_unique_is_flagged():
    # INVISIBLE UNIQUE / INVISIBLE PRIMARY KEY is Oracle's own documented
    # example usage for the modifier (hiding a unique/PK column) -- must
    # not be a false negative.
    source = "create table customers (customer_id number, ssn varchar2(11) invisible unique);\n"
    findings = find_invisible_columns(source)
    assert len(findings) == 1


def test_invisible_before_primary_key_is_flagged():
    source = "create table customers (customer_id number invisible primary key);\n"
    findings = find_invisible_columns(source)
    assert len(findings) == 1


def test_invisible_before_references_is_flagged():
    source = (
        "create table order_items (order_id number invisible references orders(order_id));\n"
    )
    findings = find_invisible_columns(source)
    assert len(findings) == 1


def test_column_literally_named_invisible_is_not_flagged():
    # The word "invisible" as an ordinary column name is always followed by
    # its own datatype, not by a comma/closing-paren/NOT/DEFAULT/ENCRYPT --
    # that's what distinguishes it from the real trailing modifier.
    source = "create table t (id number, invisible number);\n"
    assert find_invisible_columns(source) == []


def test_ordinary_table_is_not_flagged():
    source = "create table orders (order_id number);\n"
    assert find_invisible_columns(source) == []


def test_unterminated_statement_does_not_bleed_into_an_earlier_table():
    # DBMS_METADATA.GET_DDL's default output (this project's own
    # documented Oracle export mechanism) has no trailing ';' -- scoping
    # "this table's own text" to just "next ';' or end of file" used to
    # let a later table's own INVISIBLE column bleed all the way back to
    # an earlier, unrelated, unterminated table.
    source = (
        "create table small_lookup (id number)\n"
        "create table customers (customer_id number, legacy_code varchar2(10) invisible)\n"
    )
    findings = find_invisible_columns(source)
    assert len(findings) == 1
    assert findings[0].object_name == "CUSTOMERS"
