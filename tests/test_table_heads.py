"""Every table-level detector used to find its tables with its own copy
of r"CREATE\\s+TABLE", so any other way of writing the head hid the whole
column list from all of them at once: a MySQL CREATE TABLE IF NOT EXISTS
lost four of its five findings (and the fifth came out as table "IF"), a
TEMPORARY table lost all of them, and an Oracle GLOBAL TEMPORARY table was
never checked for ROWID, DEFAULT ON NULL or identity columns.

Each of these was run through real ora2pg 25.0 before being included:
a GLOBAL TEMPORARY table becomes CREATE TEMPORARY TABLE with ROWID -> oid
and DEFAULT ON NULL copied verbatim, and a MySQL TEMPORARY table comes out
with the missing enum type and the KEY stub of any other table -- so
their columns carry the same gaps. (Both IF NOT EXISTS and MySQL's
TEMPORARY are mangled by ora2pg in ways of their own; those are separate
gaps, not these.) The head now comes from one TABLE_HEAD per lexer."""

import pytest

from ora2pg_gap_report.core import scan_source

# Gaps that are about the head itself rather than the columns, and so are
# expected on a variant and not on the plain CREATE TABLE.
_HEAD_GAPS = {
    "global_temp_table",
    "table_if_not_exists",
    "mysql_create_table_if_not_exists",
    "mysql_temporary_table",
}

MYSQL_BODY = (
    " t (id int NOT NULL, s ENUM('a','b'),"
    " u timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,"
    " KEY k (s), CONSTRAINT f FOREIGN KEY (id) REFERENCES p(id))"
    " ENGINE=InnoDB AUTO_INCREMENT=5;"
)
ORACLE_BODY = (
    " t (id NUMBER GENERATED ALWAYS AS IDENTITY (START WITH 1),"
    " s VARCHAR2(10) DEFAULT ON NULL 'x', r ROWID)"
)


def _findings(source: str, dialect: str) -> list[tuple[str, str]]:
    return sorted(
        (f.detector, f.object_name) for f in scan_source(source, dialect) if f.detector not in _HEAD_GAPS
    )


@pytest.mark.parametrize(
    "head",
    ["CREATE TABLE IF NOT EXISTS", "CREATE TEMPORARY TABLE", "create temporary table if not exists"],
)
def test_a_mysql_table_head_variant_is_scanned_like_a_plain_create_table(head):
    assert _findings(head + MYSQL_BODY, "mysql") == _findings("CREATE TABLE" + MYSQL_BODY, "mysql")


@pytest.mark.parametrize("head", ["CREATE GLOBAL TEMPORARY TABLE", "CREATE TABLE IF NOT EXISTS"])
def test_an_oracle_table_head_variant_is_scanned_like_a_plain_create_table(head):
    plain = _findings("CREATE TABLE" + ORACLE_BODY + ";", "oracle")
    assert {"default_on_null", "identity_column", "rowid_type"} <= {d for d, _ in plain}
    assert _findings(head + ORACLE_BODY + " ON COMMIT PRESERVE ROWS;", "oracle") == plain


def test_the_mysql_table_name_is_not_taken_from_if_not_exists():
    names = {f.object_name for f in scan_source("CREATE TABLE IF NOT EXISTS `orders`" + MYSQL_BODY[2:], "mysql")}
    assert names == {"ORDERS"}
