from ora2pg_gap_report.detectors.mssql_filtered_index import find_mssql_filtered_indexes


def test_the_construct_is_flagged():
    source = "CREATE NONCLUSTERED INDEX IX_alive ON soft_del (id) WHERE deleted = 0;\n"
    findings = find_mssql_filtered_indexes(source)
    assert len(findings) == 1
    assert findings[0].object_name == 'UNKNOWN'
    assert findings[0].snippet == 'filtered INDEX'
    assert findings[0].severity == "high"
    assert findings[0].line == 1

def test_a_unique_filtered_index_is_flagged():
    source = "CREATE UNIQUE NONCLUSTERED INDEX UX_a ON t (a) WHERE a IS NOT NULL;\n"
    assert len(find_mssql_filtered_indexes(source)) == 1


def test_an_include_index_is_not_flagged():
    # Verified: ora2pg converts this one correctly, into a real CREATE INDEX.
    assert find_mssql_filtered_indexes('CREATE NONCLUSTERED INDEX IX_a ON t (a) INCLUDE (b, c);\n') == []

def test_a_plain_index_is_not_flagged():
    # No filter, nothing lost.
    assert find_mssql_filtered_indexes('CREATE INDEX IX_a ON t (a);\n') == []

def test_a_select_with_a_where_is_not_flagged():
    # A WHERE outside a CREATE INDEX is not a filtered index.
    assert find_mssql_filtered_indexes('CREATE PROCEDURE dbo.p AS BEGIN SELECT a FROM t WHERE b = 1; END;\n') == []
