# GAP-144: a parameter default written `type:= value`

Oracle feature: `:=` needs no spaces around it: `a_delimiter varchar2:= chr(10)`, `a_base integer :=0`.

## How it was found

Running --migrate --load-check on other people's code (utPLSQL, OraOpenSource Logger, the Alexandria PL/SQL library, Oracle's sample schemas) and reading the errors no known gap explained.

## Minimal example

`tests/fixtures/corpus_gaps/oracle_functions.sql`, VALID in a live Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_c1(a_item VARCHAR2, a_c VARCHAR2:= '.', a_base INTEGER :=0) RETURN VARCHAR2 IS
BEGIN
  RETURN trim(leading a_c from a_item) || '|' || trim(trailing a_c from a_item) || '|' || a_base;
END;
/
```

## ora2pg output (v25.0)

```sql
CREATE OR REPLACE FUNCTION gx_c1 (a_item text, a_c VARCHAR2DEFAULT '.', a_base integer DEFAULT0) RETURNS varchar AS $body$
```

The `:=` becomes DEFAULT glued to its neighbours, and `VARCHAR2` is not even converted. In a declaration (`v NUMBER:=0;`) the `:=` is copied and loads.

## Observed problem

The function does not load:

```
ERROR:  syntax error at or near "'.'"
```

Found in utPLSQL: seven functions of `ut_utils` (`a_delimiter varchar2:= chr(10)`) and `get_fixed_size_hash` (`a_base integer :=0`).

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** `--prepare` puts the spaces in routine parameter lists (`prepare_oracle_param_default_spacing`); ora2pg then writes `a_c text DEFAULT '.', a_base integer DEFAULT 0`, checked: the function loads and returns what Oracle does.

Implemented: `ora2pg_gap_report/detectors/param_default_spacing.py`.
