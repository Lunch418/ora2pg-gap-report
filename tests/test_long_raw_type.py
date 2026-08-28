from ora2pg_gap_report.detectors.long_raw_type import find_long_raw_columns


def test_a_long_raw_column_is_flagged():
    source = (
        "CREATE TABLE docs (\n"
        "    id     NUMBER PRIMARY KEY,\n"
        "    blobby LONG RAW\n"
        ");\n"
    )
    findings = find_long_raw_columns(source)
    assert len(findings) == 1
    assert findings[0].object_name == "DOCS"
    assert findings[0].snippet == "LONG RAW"
    assert findings[0].severity == "high"
    assert findings[0].line == 3


def test_a_plain_long_column_is_not_flagged():
    # LONG is Oracle's legacy *character* type and `LONG:text` is both
    # ora2pg's documented mapping and the correct one.
    source = "CREATE TABLE docs (id NUMBER, body LONG);\n"
    assert find_long_raw_columns(source) == []


def test_raw_and_blob_columns_are_not_flagged():
    # Both are mapped to bytea correctly in the same ora2pg run.
    source = "CREATE TABLE t (a RAW(200), b BLOB, c BFILE);\n"
    assert find_long_raw_columns(source) == []


def test_the_mixed_column_list_from_the_research_doc_flags_only_long_raw():
    source = (
        "CREATE TABLE binstuff (\n"
        "    id       NUMBER PRIMARY KEY,\n"
        "    a_raw    RAW(200),\n"
        "    a_long   LONG,\n"
        "    a_lraw   LONG RAW,\n"
        "    a_blob   BLOB,\n"
        "    a_clob   CLOB,\n"
        "    a_bfile  BFILE\n"
        ");\n"
    )
    findings = find_long_raw_columns(source)
    assert len(findings) == 1
    assert findings[0].line == 5
