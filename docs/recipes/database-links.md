*English | [Русский](database-links.ru.md)*

# Database links -> postgres_fdw

Covers: GAP-006 (`database_link`).

## The problem

`SELECT ... FROM employees@hr_link` reads a table in another database
through a database link. `ora2pg` copies the reference as it is, and
PostgreSQL has no `@` syntax, so the statement fails. The PostgreSQL way
to reach another database is a foreign data wrapper: `postgres_fdw` for
another PostgreSQL database (it ships with PostgreSQL), `oracle_fdw` when
the other side stays on Oracle.

## The pattern: one schema per link

Name a local schema after the link and import the remote tables into it.
Then `employees@hr_link` becomes `hr_link.employees`, a mechanical
rewrite of every reference, with no other change to the query.

```sql
CREATE EXTENSION IF NOT EXISTS postgres_fdw;

-- CREATE DATABASE LINK hr_link CONNECT TO hr IDENTIFIED BY ... USING 'hrdb';
CREATE SERVER hr_link
    FOREIGN DATA WRAPPER postgres_fdw
    OPTIONS (host 'localhost', dbname 'postgres');

-- The credentials live in the user mapping, not in the code.
CREATE USER MAPPING FOR CURRENT_USER
    SERVER hr_link
    OPTIONS (user 'postgres');

CREATE SCHEMA hr_link;
```

Bring in the remote tables, all of them or a list:

```pgsql
IMPORT FOREIGN SCHEMA public LIMIT TO (employees, departments)
    FROM SERVER hr_link INTO hr_link;
```

or declare one by hand when you need only some columns or another name.
The check below declares a foreign table over a catalog view that exists in
every database, and reads it across the link:

```sql
CREATE FOREIGN TABLE hr_link.remote_schemas (nspname name)
    SERVER hr_link
    OPTIONS (schema_name 'pg_catalog', table_name 'pg_namespace');

DO $$
BEGIN
    -- SELECT count(*) FROM pg_namespace@hr_link
    ASSERT (SELECT count(*) FROM hr_link.remote_schemas WHERE nspname = 'pg_catalog') = 1;
END $$;
```

The rewrite of the references themselves can be done with one regular
expression over the generated code (`(\w+)@(\w+)` -> `\2.\1`), then
reviewed: it is the same query, now reading `hr_link.employees`.

## What does not carry over

- **Remote procedure calls.** `hr_pkg.raise_salary@hr_link(...)` cannot go
  through a foreign table. Use the `dblink` extension:
  `SELECT dblink_exec('hr_link', 'CALL hr_pkg_raise_salary(...)')`, where
  `hr_link` can be the same foreign server (`dblink` accepts a server name).
- **Distributed transactions.** Oracle commits both sides of a link with
  two-phase commit. `postgres_fdw` commits the remote side when the local
  transaction commits, but not atomically with it: a failure in between
  can leave one side committed. Code that writes to both databases and
  relies on all-or-nothing needs a different design (one database, or an
  outbox table processed afterwards).
- **Synonyms over links.** `CREATE SYNONYM emp FOR employees@hr_link` is a
  view in PostgreSQL: `CREATE VIEW emp AS SELECT * FROM hr_link.employees`.

## Watch out for

- **Performance.** `postgres_fdw` pushes `WHERE`, joins between tables of
  the same server, sorts and aggregates to the remote side, but not
  everything. Check the plan of every query that used a link
  (`EXPLAIN VERBOSE` shows the remote SQL), and add `use_remote_estimate
  'true'` to the server options when join orders come out wrong.
- **Who may connect.** A non-superuser needs a password in the user
  mapping. Create one mapping per role that uses the link, or one `FOR
  PUBLIC` for a shared technical account.
- **An isolated network.** A link that crossed a security boundary in
  Oracle still does in PostgreSQL. The wrapper does not change what is
  allowed to talk to what; check with whoever owns that boundary.
