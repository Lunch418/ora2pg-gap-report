# GAP-032: `CREATE [PUBLIC] SYNONYM` loses the target object's schema

Oracle feature: `CREATE [PUBLIC] SYNONYM name FOR [schema.]object` — an
alias for an object, often in another schema. The usual practice is a
synonym with the same base name as the target table (`CREATE PUBLIC
SYNONYM employees FOR hr.employees`), so that users of other schemas can
write `employees` without naming the owner.

## Minimal example

```sql
CREATE TABLE hr.employees (emp_id NUMBER);
CREATE PUBLIC SYNONYM employees FOR hr.employees;
```

## ora2pg output (v25.0, `-t SYNONYM`)

```sql
CREATE OR REPLACE VIEW employees AS SELECT * FROM employees;
```

The synonym is converted into a `VIEW`, but the target object loses its
schema entirely — `hr.employees` becomes plain `employees`, unqualified.
Also checked with differing base names (`CREATE PUBLIC SYNONYM employees
FOR hr.emp_table`) — the same result, `SELECT * FROM emp_table` with no
schema.

## Observed problem

When the synonym's name matches the target table's base name — the most
common case in practice, since that is usually the whole point of a
synonym — the result is a self-referencing `VIEW`. Confirmed against a real
PostgreSQL 16:

```sql
CREATE SCHEMA hr;
CREATE TABLE hr.employees (emp_id bigint);
CREATE OR REPLACE VIEW employees AS SELECT * FROM employees;
-- ERROR:  relation "employees" does not exist
-- LINE 1: CREATE OR REPLACE VIEW employees AS SELECT * FROM employees;
```

The migration script stops right at this object. When the names differ
there is no failure at this stage, but the view still relies on an
unqualified name — which `emp_table` it resolves to depends entirely on
the `search_path` at the moment that `CREATE VIEW` runs, not on the
original Oracle binding to `hr.emp_table`. If a same-named table from
another schema happens to be on the `search_path` — routine when several
Oracle schemas are migrated into one PostgreSQL database — the view binds
silently to the wrong table, with no error at all.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/public_synonym.py`.
