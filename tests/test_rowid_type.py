from ora2pg_gap_report.detectors.rowid_type import find_rowid_types


def test_rowid_column_is_flagged():
    source = "create table orders (order_id number, row_ref rowid);\n"
    findings = find_rowid_types(source)
    assert len(findings) == 1
    assert findings[0].object_name == "ORDERS"
    assert findings[0].severity == "high"
    assert "ROWID" in findings[0].snippet.upper()


def test_urowid_with_size_is_flagged():
    source = "create table orders (order_id number, row_ref urowid(4000));\n"
    findings = find_rowid_types(source)
    assert len(findings) == 1
    assert "UROWID" in findings[0].snippet.upper()


def test_ordinary_column_types_are_not_flagged():
    source = "create table orders (order_id number, status varchar2(20));\n"
    assert find_rowid_types(source) == []


def test_column_named_rowid_ref_is_not_a_false_positive():
    # 'rowid_ref' as a single identifier (e.g. used for the column name
    # itself, not the type) must not match -- there's no whitespace
    # between ROWID and the rest, unlike the real trailing type keyword.
    source = "create table orders (order_id number, rowid_ref varchar2(18));\n"
    assert find_rowid_types(source) == []


def test_multiple_rowid_columns_in_one_table_are_each_flagged():
    source = (
        "create table orders (\n"
        "  order_id number,\n"
        "  old_ref rowid,\n"
        "  new_ref urowid\n"
        ");\n"
    )
    findings = find_rowid_types(source)
    assert len(findings) == 2


def test_rowid_is_not_misattributed_to_a_later_unrelated_table():
    source = (
        "create table snapshot_a (id number, ref rowid);\n"
        "create table live_b (id number);\n"
    )
    findings = find_rowid_types(source)
    assert len(findings) == 1
    assert findings[0].object_name == "SNAPSHOT_A"


def test_unterminated_statement_does_not_bleed_into_an_earlier_table():
    source = (
        "create table small_lookup (id number)\n"
        "create table orders (order_id number, ref rowid)\n"
    )
    findings = find_rowid_types(source)
    assert len(findings) == 1
    assert findings[0].object_name == "ORDERS"


def test_reported_line_is_the_column_definition_line():
    source = (
        "create table orders (\n"
        "  order_id number,\n"
        "  row_ref rowid\n"
        ");\n"
    )
    findings = find_rowid_types(source)
    assert len(findings) == 1
    assert findings[0].line == 3


def test_double_quoted_rowid_column_is_flagged():
    source = 'create table orders (order_id number, "ROW_REF" rowid);\n'
    findings = find_rowid_types(source)
    assert len(findings) == 1
    assert findings[0].object_name == "ORDERS"


def test_rowid_pseudocolumn_in_ctas_select_is_not_a_false_positive():
    # 'CREATE TABLE ... AS SELECT ROWID rid, ...' is a common dedup/
    # diagnostic-table idiom -- ROWID there is the pseudocolumn in the
    # SELECT list, not a column-type declaration; a CTAS has no
    # column-type list at all for this detector to look at.
    source = "create table dedup_ids as select rowid rid, order_id from orders where order_id is null;\n"
    assert find_rowid_types(source) == []


def test_ctas_with_explicit_column_name_list_but_no_types_is_not_flagged():
    # Oracle also allows CTAS with an explicit column *name* list (no
    # types -- types come from the SELECT) -- this must not be confused
    # with an ordinary column-definition list.
    source = "create table dedup_ids (rid, order_id) as select rowid, order_id from orders;\n"
    assert find_rowid_types(source) == []
