from ora2pg_gap_report.detectors.mysql_index_name_collision import find_mysql_index_name_collision
from ora2pg_gap_report.prepare import prepare_mysql_indexes

SOURCE = (
    "CREATE TABLE `orders` (`id` int, `customer_id` int, KEY `customer_id` (`customer_id`), KEY `own` (`id`));\n"
    "CREATE TABLE `invoices` (`id` int, `customer_id` int, KEY `customer_id` (`customer_id`));\n"
    "CREATE TABLE `refunds` (`id` int, `customer_id` int, INDEX customer_id (`customer_id`), UNIQUE KEY `own` (`id`));\n"
)


def test_a_name_on_several_tables_is_flagged_after_the_first():
    assert [(f.object_name, f.line, f.snippet) for f in find_mysql_index_name_collision(SOURCE)] == [
        ("invoices", 2, "customer_id"),
        ("refunds", 3, "customer_id"),
    ]


def test_unique_keys_and_names_on_one_table_are_not_collisions():
    # A UNIQUE KEY becomes a constraint whose name ora2pg drops.
    source = "CREATE TABLE `a` (`x` int, UNIQUE KEY `k` (`x`));\nCREATE TABLE `b` (`x` int, UNIQUE KEY `k` (`x`), KEY `j` (`x`));\n"
    assert find_mysql_index_name_collision(source) == []


def test_prepare_renames_every_clashing_name_after_its_table():
    out, _ = prepare_mysql_indexes(SOURCE)
    assert "INDEX `orders_customer_id` (`customer_id`)" in out
    assert "INDEX `invoices_customer_id` (`customer_id`)" in out
    assert "INDEX `refunds_customer_id` (`customer_id`)" in out
    assert "INDEX `own` (`id`)" in out and "UNIQUE KEY `own` (`id`)" in out
    assert find_mysql_index_name_collision(out) == []
