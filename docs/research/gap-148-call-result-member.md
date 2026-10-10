# GAP-148: a member of a call's result - `f(x).y` becomes `f[x].y`

Oracle feature: a call's result can be used straight away: `p_xml.extract('/a').getstringval()`, `get_rec(1).name`.

## How it was found

Running --migrate --load-check on other people's code (utPLSQL, OraOpenSource Logger, the Alexandria PL/SQL library, Oracle's sample schemas) and reading the errors no known gap explained.

## Minimal example

`tests/fixtures/corpus_gaps/oracle_functions.sql`, VALID in a live Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_c4(p_xml XMLTYPE) RETURN VARCHAR2 IS
BEGIN
  RETURN p_xml.extract('/a/text()').getstringval();
END;
/
```

## ora2pg output (v25.0)

```sql
  RETURN p_xml.extract['/a/text()'].getstringval();
```

ora2pg has a rule (`PLSQL.pm`) that rewrites `name(args).field` into `name[args].field` - right for a collection element's field, `t(i).name` - and applies it to a call as well.

## Observed problem

The function does not load (Oracle 23ai: `gx_c4(XMLTYPE('<a>hi</a>'))` = `hi`):

```
ERROR:  syntax error at or near "("
```

Found in the Alexandria PL/SQL library: `l_xml.extract('...').getstringval()` in the Amazon S3, FTP and web service packages.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** Keep the call's result in a variable, or rewrite it with PostgreSQL's functions (`xpath(...)` for XML). The detector skips a name declared as a variable or parameter - a collection, which the rule is for.

Implemented: `ora2pg_gap_report/detectors/call_result_member.py`.
