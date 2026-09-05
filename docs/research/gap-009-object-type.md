# GAP-009: `CREATE TYPE ... AS OBJECT` / `TYPE BODY` — outside the effort estimate entirely

Oracle feature: an object type (`CREATE TYPE name AS OBJECT (attributes,
MEMBER methods)` plus a separate `CREATE TYPE BODY` with the method
implementations) — Oracle-specific OOP layered over SQL.

## What is actually wrong here

This gap differs in character from the others in the project. It is not
"ora2pg silently mangles the code" but "ora2pg does not attempt to
estimate the cost of such an object at all".

## Minimal example

```sql
CREATE OR REPLACE TYPE point_t AS OBJECT (
  x NUMBER,
  y NUMBER,
  MEMBER FUNCTION distance_to(p point_t) RETURN NUMBER
);
/
CREATE OR REPLACE TYPE BODY point_t AS
  MEMBER FUNCTION distance_to(p point_t) RETURN NUMBER IS
  BEGIN
    RETURN SQRT(POWER(x - p.x, 2) + POWER(y - p.y, 2));
  END distance_to;
END;
/
```

## ora2pg output (v25.0, `-t TYPE`)

ora2pg marks the output honestly: `-- Unsupported, please edit to match
PostgreSQL syntax`, and copies the Oracle syntax as written under that
note. That in itself is not the finding — it is already an explicit
warning from ora2pg.

The finding is elsewhere: running `ora2pg -t TYPE -i ... --estimate_cost`
**returns nothing at all** — no report line, no cost figure. Judging by
the code and by a direct run, `--estimate_cost` has no estimation
mechanism for `TYPE` objects whatsoever; it is built only for
`PACKAGE`/`TRIGGER`/`FUNCTION`/`PROCEDURE`.

## Observed problem

A schema making substantial use of Oracle object types — typical of older,
OOP-oriented enterprise codebases — will get a **zero** contribution to the
effort estimate from `--estimate_cost`/`SHOW_REPORT` for those objects:
not an understated figure, but the complete absence of any figure. And
migrating object types with methods is one of the most labour-intensive
tasks there is: PostgreSQL has no object types with methods, only composite
types (data structures without behaviour), so rewriting requires an
architectural decision (a `composite type` plus separate functions called
explicitly, not through `obj.method()`), not just a syntactic
substitution.

**Reproducible: YES** (from the code, and from an `--estimate_cost` run
that returned an empty result). Ora2Pg version: 25.0.

## Verdict

**Gap confirmed**, though not in the spirit of "ora2pg lies" so much as
"ora2pg is silent exactly where it should be loudest". Implemented in
`ora2pg_gap_report/detectors/object_type.py`.
