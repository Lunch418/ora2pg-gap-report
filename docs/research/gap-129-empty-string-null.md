# GAP-129: `''` is NULL in Oracle and an empty string in PostgreSQL

Oracle feature: a zero-length string literal is NULL. `x = ''` is never
true, `v := ''` leaves `v` NULL, `DEFAULT ''` is no default at all, and
`NVL(p, '')` returns NULL.

## How it was found

From an outside review of the tool: everything it reported failed at load
time, and nothing that loads and then runs differently. `''` vs NULL is the
best-known difference of that kind, so it was checked first.

## Minimal example

`tests/fixtures/empty_string_null/oracle_source.sql`, VALID in a live
Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_e2(p VARCHAR2) RETURN VARCHAR2 IS
BEGIN
  IF p = '' THEN RETURN 'empty'; END IF;
  RETURN 'other';
END;
/
CREATE OR REPLACE FUNCTION gx_e5(p VARCHAR2) RETURN VARCHAR2 IS
  v VARCHAR2(10) := '';
BEGIN
  IF v IS NULL THEN RETURN 'v is null'; END IF;
  RETURN 'v is not null';
END;
/
CREATE TABLE gx_notes (id NUMBER, note VARCHAR2(20) DEFAULT '');
CREATE OR REPLACE FUNCTION gx_e6(p VARCHAR2) RETURN VARCHAR2 IS
BEGIN
  RETURN NVL(p, '');
END;
/
```

plus three functions that only pass values through (`p IS NULL`, `a || b`,
`LENGTH(p)`), to see what happens to a `''` argument.

## ora2pg output (v25.0, `-t FUNCTION`, `-t TABLE`)

`tests/fixtures/empty_string_null/ora2pg_output.sql`. Everything is copied
as it is, except NVL:

```sql
  IF p = '' THEN RETURN 'empty';END IF;
  v varchar(10) := '';
	note varchar(20) DEFAULT ''
  RETURN coalesce(p, '');
```

ora2pg has a `NULL_EQUAL_EMPTY` option that rewrites comparisons with
`''`; it is off by default and was off here.

## Observed problem

All of it loads in PostgreSQL 16 with no error, and then:

| Call | Oracle 23ai | PostgreSQL 16 |
|---|---|---|
| `gx_e2('')` | `other` | `empty` |
| `gx_e5('x')` | `v is null` | `v is not null` |
| `INSERT INTO gx_notes (id) VALUES (1)`, rows with `note IS NULL` | 1 | 0 (`note` is `''`) |
| `gx_e6(NULL) IS NULL` | yes | no (`''`) |
| `gx_e1('')` (`p IS NULL`) | `null` | `value` |
| `gx_e3('a', NULL)` (`a \|\| b`) | `a` | NULL |
| `gx_e4('')` (`LENGTH`) | NULL | 0 |

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage semantic.** Nothing fails;
the results are different.

What can be found in the text: an empty literal compared (`=`, `<>`, `!=`,
`^=`, either side), assigned (`:=`), as a `DEFAULT`, or as the fallback of
`NVL`/`COALESCE`. The detector reports those. The other three rows of the
table - `IS NULL` on a value that came in as `''`, concatenation with NULL,
`LENGTH('')` - depend on the data, not on the code, and cannot be told
from ordinary use by reading the source; they are left to testing.

There is no mechanical fix: whether `x = ''` should become `x IS NULL` or
`coalesce(x, '') = ''` depends on whether the data in PostgreSQL can hold
empty strings. `--verify` re-runs the detector on the output: ora2pg keeps
every shape, NVL as `coalesce(x, '')`, which it also finds.

Implemented: `ora2pg_gap_report/detectors/empty_string_null.py`.
