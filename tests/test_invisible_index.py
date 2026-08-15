from ora2pg_gap_report.detectors.invisible_index import find_invisible_indexes


def test_invisible_index_is_flagged():
    source = "create index orders_status_idx on orders(status) invisible;\n"
    findings = find_invisible_indexes(source)
    assert len(findings) == 1
    assert findings[0].object_name == "ORDERS_STATUS_IDX"
    assert findings[0].severity == "medium"


def test_unique_and_bitmap_indexes_are_also_covered():
    unique_source = "create unique index idx1 on t(c) invisible;\n"
    bitmap_source = "create bitmap index idx2 on t(c) local invisible;\n"
    assert len(find_invisible_indexes(unique_source)) == 1
    assert len(find_invisible_indexes(bitmap_source)) == 1


def test_ordinary_visible_index_is_not_flagged():
    source = "create index idx1 on t(c);\n"
    assert find_invisible_indexes(source) == []


def test_invisible_index_is_not_misattributed_to_a_later_unrelated_index():
    source = (
        "create index idx1 on t1(c) invisible;\n"
        "create index idx2 on t2(c);\n"
    )
    findings = find_invisible_indexes(source)
    assert len(findings) == 1
    assert findings[0].object_name == "IDX1"


def test_unterminated_statement_does_not_bleed_into_an_earlier_index():
    # DBMS_METADATA.GET_DDL's default output (this project's own
    # documented Oracle export mechanism) has no trailing ';' -- scoping
    # "this index's own text" to just "next ';' or end of file" used to
    # let a later index's own INVISIBLE modifier bleed all the way back
    # to an earlier, unrelated, unterminated index.
    source = (
        "create index idx1 on t1(c)\n"
        "create index idx2 on t2(c) invisible\n"
    )
    findings = find_invisible_indexes(source)
    assert len(findings) == 1
    assert findings[0].object_name == "IDX2"


def test_reported_line_is_the_invisible_token_not_the_create_index_line():
    source = (
        "create index orders_status_idx\n"
        "  on orders(status)\n"
        "  invisible;\n"
    )
    findings = find_invisible_indexes(source)
    assert len(findings) == 1
    assert findings[0].line == 3


def test_column_literally_named_invisible_is_not_a_false_positive():
    # A column being indexed can plausibly be named "invisible" (e.g. a
    # boolean flag) -- unlike the real trailing modifier, it's always
    # immediately followed by ',' or ')' inside the column list.
    source = "create index idx_flags on widgets(invisible, other_col);\n"
    assert find_invisible_indexes(source) == []


def test_double_quoted_column_named_invisible_is_not_a_false_positive():
    # mask_strings_and_comments() only masks single-quoted string
    # literals/comments, never double-quoted identifiers -- a column
    # named "INVISIBLE" (valid Oracle identifier syntax) must not be
    # confused with the real modifier.
    source = 'create index idx_flags on widgets("invisible");\n'
    assert find_invisible_indexes(source) == []
