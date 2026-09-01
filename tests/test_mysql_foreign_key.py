from ora2pg_gap_report.detectors.mysql_foreign_key import find_mysql_foreign_keys


def test_a_named_constraint_foreign_key_is_flagged():
    source = (
        "CREATE TABLE `orders2` (\n"
        "  `id` int(11) NOT NULL,\n"
        "  `customer_id` int(11) NOT NULL,\n"
        "  PRIMARY KEY (`id`),\n"
        "  CONSTRAINT `fk_oc` FOREIGN KEY (`customer_id`) "
        "REFERENCES `customers` (`id`) ON DELETE CASCADE\n"
        ") ENGINE=InnoDB;\n"
    )
    findings = find_mysql_foreign_keys(source)
    assert len(findings) == 1
    assert findings[0].object_name == "ORDERS2"
    assert findings[0].snippet == "FOREIGN KEY"
    assert findings[0].severity == "high"
    assert findings[0].line == 5


def test_the_bare_foreign_key_form_is_flagged_too():
    source = "CREATE TABLE child (id INT, pid INT, FOREIGN KEY (pid) REFERENCES parent (id));\n"
    assert len(find_mysql_foreign_keys(source)) == 1


def test_a_table_without_foreign_keys_is_not_flagged():
    assert find_mysql_foreign_keys("CREATE TABLE t (id INT PRIMARY KEY);\n") == []


def test_a_plain_key_clause_is_not_flagged():
    assert find_mysql_foreign_keys("CREATE TABLE t (a INT, KEY k (a));\n") == []


def test_a_bare_ctas_with_no_column_list_is_not_flagged():
    assert find_mysql_foreign_keys("CREATE TABLE t AS SELECT * FROM other;\n") == []
