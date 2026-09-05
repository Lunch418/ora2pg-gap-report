# GAP-006: `table@dblink_name` — direct database-link references in SQL

Oracle feature: `SELECT ... FROM table@dblink_name` — a direct reference to
an object in a remote database through a `DATABASE LINK` inside an ordinary
SQL query (not `CREATE DATABASE LINK` itself, but its use in queries).
Common in integration and ERP scenarios — exchanging data between schemas
or databases without an intermediate layer.

## Minimal example

```sql
CREATE OR REPLACE PACKAGE BODY remote_sync_pkg AS
  PROCEDURE pull_remote_orders IS
  BEGIN
    INSERT INTO local_orders (order_id, customer_id, amount)
    SELECT order_id, customer_id, amount
    FROM orders@remote_erp_link
    WHERE created_at > SYSDATE - 1;
    COMMIT;
  END pull_remote_orders;
END remote_sync_pkg;
/
```

## ora2pg output (v25.0, `-t PACKAGE`)

`orders@remote_erp_link` is copied verbatim — `@remote_erp_link` stays
attached to the table name, unchanged.

## Observed problem

Confirmed against a real PostgreSQL 16: `@` is not valid SQL syntax in
PostgreSQL at all (the character is not allowed in an unquoted table name).
`CREATE PROCEDURE` succeeds without error (`check_function_bodies = false`
in ora2pg's output); it fails only on the first real call:

```
ERROR:  syntax error at or near "@"
LINE 3:     FROM orders@remote_erp_link
```

PostgreSQL has an architectural equivalent (the `postgres_fdw`/`dblink`
extensions plus `IMPORT FOREIGN SCHEMA`/foreign tables), but that requires
configuring a foreign server by hand and cannot be substituted for
`@dblink_name` automatically without knowing the remote database's real
connection parameters — which is why this is a gap rather than something
that could be converted automatically in principle.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Valuable in particular because it is a common pattern in
integrated Oracle systems (exchange between schemas and databases), not a
rare piece of syntactic exotica.

Implemented in `ora2pg_gap_report/detectors/database_link.py`.
