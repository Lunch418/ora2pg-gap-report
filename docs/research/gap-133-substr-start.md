# GAP-133: `SUBSTR` from position 0 or a negative position

Oracle feature: in `SUBSTR(s, pos[, len])` a `pos` of 0 is read as 1, and a
negative `pos` counts from the end of the string.

## How it was found

Among the functions compared on Oracle 23ai and PostgreSQL 16 for
GAP-129..132.

## Minimal example

`tests/fixtures/silent_numbers/oracle_functions.sql`, VALID in a live
Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_s1(p VARCHAR2) RETURN VARCHAR2 IS
BEGIN
  RETURN SUBSTR(p, 0, 3) || '|' || SUBSTR(p, -3) || '|' || SUBSTR(p, -3, 2)
      || '|' || SUBSTR(p, 0) || '|' || SUBSTR(p, 2, 2);
END;
/
```

## ora2pg output (v25.0)

The call is copied as it is. PostgreSQL has `substr`, so it loads.

## Observed problem

PostgreSQL's `substr` counts positions before the first character as real
ones:

| | Oracle 23ai | PostgreSQL 16 |
|---|---|---|
| `SUBSTR('abcdef', 0, 3)` | `abc` | `ab` |
| `SUBSTR('abcdef', -3)` | `def` | `abcdef` |
| `SUBSTR('abcdef', -3, 2)` | `de` | `` (empty) |
| `SUBSTR('abcdef', 0)` | `abcdef` | `abcdef` |
| `SUBSTR('abcdef', 2, 2)` | `bc` | `bc` |

Found in `docs/research/samples/file_util_pkg.pkb`: `substr(p_dir, -1) =
g_dir_sep_win` - the last character in Oracle, the whole path in
PostgreSQL, so the check is never true.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage semantic.** Write 1 for 0;
from the end, `right(s, n)` or `substr(s, length(s) - n + 1, len)`.

The detector flags a literal 0 with a length and any negative literal.
`SUBSTR(s, 0)` is the same in both; a position held in a variable cannot be
read from the text.

Implemented: `ora2pg_gap_report/detectors/substr_start.py`.
