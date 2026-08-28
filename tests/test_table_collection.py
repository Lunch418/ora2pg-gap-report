from ora2pg_gap_report.detectors.table_collection import find_table_collection_operator


def test_the_table_operator_in_a_from_clause_is_flagged():
    source = "SELECT t.column_value\n  FROM TABLE(get_ids(42)) t;\n"
    findings = find_table_collection_operator(source)
    assert len(findings) == 1
    assert findings[0].snippet == "TABLE("
    assert findings[0].severity == "high"
    assert findings[0].line == 2


def test_the_operator_after_a_join_is_flagged():
    source = "SELECT * FROM orders o JOIN TABLE(o.items) i ON 1 = 1;\n"
    assert len(find_table_collection_operator(source)) == 1


def test_create_table_is_not_flagged():
    assert find_table_collection_operator("CREATE TABLE t (id NUMBER);\n") == []


def test_alter_and_truncate_table_are_not_flagged():
    source = "ALTER TABLE t ADD (c NUMBER);\nTRUNCATE TABLE t;\n"
    assert find_table_collection_operator(source) == []


def test_a_local_collection_type_declaration_is_not_flagged():
    # `TYPE t IS TABLE OF ...` belongs to GAP-003/GAP-021, not here.
    source = "DECLARE\n  TYPE id_tab IS TABLE OF NUMBER;\nBEGIN\n  NULL;\nEND;\n"
    assert find_table_collection_operator(source) == []


def test_an_ordinary_from_clause_is_not_flagged():
    assert find_table_collection_operator("SELECT * FROM employees e;\n") == []
