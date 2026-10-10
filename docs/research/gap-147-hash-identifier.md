# GAP-147: a name with `#` in it

Oracle feature: unquoted names may contain `#` (and `$`): `n#count`, `emp#`.

## How it was found

Running --migrate --load-check on other people's code (utPLSQL, OraOpenSource Logger, the Alexandria PL/SQL library, Oracle's sample schemas) and reading the errors no known gap explained.

## Minimal example

`tests/fixtures/corpus_gaps/oracle_functions.sql`, VALID in a live Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_c3(p NUMBER) RETURN NUMBER IS
  n#count NUMBER(5) := p;
BEGIN
  RETURN n#count * 2;
END;
/
```

## ora2pg output (v25.0)

```sql
  n#count integer := p;
  RETURN n#count * 2;
```

The name is copied as it is.

## Observed problem

PostgreSQL does not take `#` in a name (`$` it does):

```
ERROR:  syntax error at or near "#"
```

Found in Oracle's sample schemas: `COUNT(*) as #_OF_PRODUCTS` in a view (Oracle needs no quotes there either).

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** Rename it, or quote it in the output (`"n#count"`). Reported once per name and object.

Implemented: `ora2pg_gap_report/detectors/hash_identifier.py`.
