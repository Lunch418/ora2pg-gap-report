from ora2pg_gap_report.detectors.bitmap_index import find_bitmap_indexes


def test_bitmap_index_is_flagged():
    source = "CREATE BITMAP INDEX idx_emp_gender ON employees (gender);\n"
    findings = find_bitmap_indexes(source)
    assert len(findings) == 1
    assert findings[0].object_name == "IDX_EMP_GENDER"
    assert findings[0].snippet == "CREATE BITMAP INDEX"
    assert findings[0].severity == "high"


def test_bitmap_join_index_is_also_flagged():
    source = (
        "create bitmap join index idx_sales_cust\n"
        "on sales (customers.cust_city)\n"
        "from sales, customers\n"
        "where sales.cust_id = customers.cust_id;\n"
    )
    findings = find_bitmap_indexes(source)
    assert len(findings) == 1
    assert findings[0].object_name == "IDX_SALES_CUST"


def test_schema_qualified_index_name_is_captured():
    source = "CREATE BITMAP INDEX hr.idx_g ON hr.employees (gender);\n"
    findings = find_bitmap_indexes(source)
    assert len(findings) == 1
    assert findings[0].object_name == "HR.IDX_G"


def test_an_ordinary_index_is_not_flagged():
    source = (
        "CREATE INDEX idx_emp_name ON employees (last_name);\n"
        "CREATE UNIQUE INDEX idx_emp_email ON employees (email);\n"
    )
    assert find_bitmap_indexes(source) == []


def test_real_oracle_sample_schema_star_schema_bitmap_indexes_are_flagged():
    # Real shape from Oracle's own db-sample-schemas (sales_history):
    # textbook star-schema bitmap indexes with LOCAL/NOLOGGING clauses.
    source = (
        "CREATE BITMAP INDEX sales_prod_bix\n"
        "   ON sales (prod_id) LOCAL NOLOGGING;\n"
        "\n"
        "CREATE BITMAP INDEX sales_cust_bix\n"
        "   ON sales (cust_id) LOCAL NOLOGGING;\n"
    )
    findings = find_bitmap_indexes(source)
    assert len(findings) == 2
    assert [f.object_name for f in findings] == ["SALES_PROD_BIX", "SALES_CUST_BIX"]
