from ora2pg_gap_report.detectors.mysql_key_index import find_mysql_key_indexes


def test_a_mysqldump_shaped_key_clause_is_flagged():
    # Exactly the shape mysqldump emits: backtick-quoted everything,
    # the KEY spelling, table options after the closing paren.
    source = (
        "CREATE TABLE `orders` (\n"
        "  `id` int(11) NOT NULL AUTO_INCREMENT,\n"
        "  `customer_id` int(11) NOT NULL,\n"
        "  PRIMARY KEY (`id`),\n"
        "  KEY `idx_customer` (`customer_id`)\n"
        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;\n"
    )
    findings = find_mysql_key_indexes(source)
    assert len(findings) == 1
    assert findings[0].object_name == "ORDERS"
    assert findings[0].snippet == "KEY"
    assert findings[0].severity == "high"
    assert findings[0].line == 5


def test_two_key_clauses_are_both_flagged():
    source = "CREATE TABLE t (a INT, b INT, KEY k1 (a), KEY k2 (b));\n"
    assert len(find_mysql_key_indexes(source)) == 2


def test_the_unnamed_key_form_is_flagged_too():
    # KEY (a) doesn't break the load the way the named form does -- it
    # vanishes from the output silently instead -- but it is the same
    # dropped index either way.
    source = "CREATE TABLE t (a INT, KEY (a));\n"
    assert len(find_mysql_key_indexes(source)) == 1


def test_primary_key_is_not_flagged():
    # Converted correctly, into ALTER TABLE ... ADD PRIMARY KEY.
    assert find_mysql_key_indexes("CREATE TABLE t (id INT, PRIMARY KEY (id));\n") == []


def test_unique_key_is_not_flagged():
    # Converted correctly, into ALTER TABLE ... ADD UNIQUE.
    assert find_mysql_key_indexes("CREATE TABLE t (e VARCHAR(9), UNIQUE KEY uq (e));\n") == []


def test_the_index_spelling_is_not_flagged():
    # The same MySQL construct under its other name -- ora2pg converts
    # this one into a real CREATE INDEX, which is the whole reason the
    # KEY spelling being broken is worth a gap of its own.
    assert find_mysql_key_indexes("CREATE TABLE t (e VARCHAR(9), INDEX idx (e));\n") == []


def test_fulltext_and_spatial_keys_are_left_to_their_own_gaps():
    assert find_mysql_key_indexes("CREATE TABLE t (b TEXT, FULLTEXT KEY ft (b));\n") == []
    assert find_mysql_key_indexes("CREATE TABLE t (l POINT, SPATIAL KEY sp (l));\n") == []


def test_foreign_key_is_left_to_its_own_gap():
    source = "CREATE TABLE t (c INT, FOREIGN KEY (c) REFERENCES o (id));\n"
    assert find_mysql_key_indexes(source) == []


def test_a_bare_ctas_with_no_column_list_is_not_flagged():
    assert find_mysql_key_indexes("CREATE TABLE t AS SELECT * FROM other;\n") == []
