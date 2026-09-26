from ora2pg_gap_report.detectors.mysql_create_table_if_not_exists import (
    find_mysql_create_table_if_not_exists,
)


def test_a_top_level_create_table_if_not_exists_is_flagged():
    source = (
        "CREATE TABLE IF NOT EXISTS `customers` (\n"
        "  `id` int NOT NULL,\n"
        "  PRIMARY KEY (`id`)\n"
        ") ENGINE=InnoDB;\n"
    )
    findings = find_mysql_create_table_if_not_exists(source)
    assert [(f.object_name, f.line, f.severity) for f in findings] == [("CUSTOMERS", 1, "high")]


def test_a_temporary_table_if_not_exists_is_flagged_too():
    source = "CREATE TEMPORARY TABLE IF NOT EXISTS cart_tmp (id int NOT NULL);\n"
    assert [f.object_name for f in find_mysql_create_table_if_not_exists(source)] == ["CART_TMP"]


def test_a_plain_create_table_is_not_flagged():
    assert find_mysql_create_table_if_not_exists("CREATE TABLE customers (id int);\n") == []


def test_the_same_statement_inside_a_procedure_is_not_flagged():
    # Copied into the PL/pgSQL body as written, where PostgreSQL accepts it.
    source = (
        "DELIMITER ;;\n"
        "CREATE PROCEDURE fill_cart(p INT)\n"
        "BEGIN\n"
        "  CREATE TEMPORARY TABLE IF NOT EXISTS cart_tmp (id int NOT NULL);\n"
        "END ;;\n"
        "DELIMITER ;\n"
    )
    assert find_mysql_create_table_if_not_exists(source) == []
