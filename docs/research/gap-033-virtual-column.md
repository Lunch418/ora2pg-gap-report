# GAP-033: a virtual column loses its protection against explicit assignment (`ORA-54016`)

Oracle feature: `<column> [<type>] [GENERATED ALWAYS] AS (<expr>)
[VIRTUAL]` — a computed column. Both `GENERATED ALWAYS` and the trailing
`VIRTUAL` are optional in Oracle — the shortest form looks like
`total_value AS (item_id * quantity + net_value)`. Beyond computing the
value, Oracle additionally guarantees at server level that nothing can be
written into such a column explicitly: any attempt to pass a value for a
virtual column in an `INSERT`/`UPDATE` fails with `ORA-54016` before
execution — a guard against programming mistakes (assigning to a computed
column by accident, or deliberately "to keep the code uniform").

## Minimal example

```sql
CREATE TABLE employees (
    emp_id NUMBER,
    salary NUMBER,
    bonus  NUMBER,
    total_comp NUMBER GENERATED ALWAYS AS (salary + bonus) VIRTUAL
);
```

## ora2pg output (v25.0, `-t TABLE`)

```sql
CREATE TABLE employees (
	emp_id bigint,
	salary bigint,
	bonus bigint,
	total_comp bigint
) ;
DROP TRIGGER IF EXISTS virt_col_employees_trigger ON employees CASCADE;

CREATE OR REPLACE FUNCTION fct_virt_col_employees_trigger() RETURNS trigger AS $BODY$
BEGIN
	NEW.total_comp = (NEW.salary + NEW.bonus);
RETURN NEW;
end
$BODY$
 LANGUAGE 'plpgsql' SECURITY DEFINER;

CREATE TRIGGER virt_col_employees_trigger
        BEFORE INSERT OR UPDATE ON employees FOR EACH ROW
        EXECUTE PROCEDURE fct_virt_col_employees_trigger();
```

ora2pg carries the computation itself over correctly — not through
PostgreSQL 12+'s native `GENERATED ALWAYS AS (...) STORED`, but through a
`BEFORE INSERT OR UPDATE` trigger that recomputes the value itself. At
first glance equivalent. Also checked for both shortened forms — `...
NUMBER GENERATED ALWAYS AS (a+b)` (no `VIRTUAL`) and `total_value AS
(item_id * quantity + net_value)` (no `GENERATED ALWAYS` at all, where
ora2pg substitutes the type `text` itself with the warning "Virtual column
... has no data type defined") — both convert into the same trigger
pattern, with the same loss of protection described below.

## Observed problem

The difference is not in the computed value but in the protection against
explicit assignment. Confirmed against a real PostgreSQL 16:

```sql
INSERT INTO employees (emp_id, salary, bonus, total_comp)
VALUES (1, 100, 50, 999999);
-- INSERT 0 1  -- succeeded, with no error at all

SELECT * FROM employees;
--  emp_id | salary | bonus | total_comp
-- --------+--------+-------+------------
--       1 |    100 |    50 |        150
```

On Oracle that same `INSERT` with an explicit `total_comp => 999999` would
have failed with `ORA-54016` before writing anything. After migration it
is quietly accepted, and the trigger silently replaces the supplied value
with the computed one, without a warning and without an error. The final
value in the column is correct (`150`), so this is not data loss — but
early diagnosis is lost: code that passes a value into a computed column
by mistake (or to keep its logic uniform with non-virtual columns) would
have been caught immediately in testing on Oracle, and goes unnoticed
after migration.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/virtual_column.py`.
