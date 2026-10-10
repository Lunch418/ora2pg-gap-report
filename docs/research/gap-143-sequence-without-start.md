# GAP-143: a sequence without START WITH

Oracle feature: `START WITH` is optional; a sequence starts at its MINVALUE (1), or MAXVALUE (-1) going down.

## How it was found

Running --migrate --load-check on other people's code (utPLSQL, OraOpenSource Logger, the Alexandria PL/SQL library, Oracle's sample schemas) and reading the errors no known gap explained.

## Minimal example

`tests/fixtures/corpus_gaps/oracle_sequences.sql`, VALID in a live Oracle 23ai:

```sql
CREATE SEQUENCE gx_cs1 CACHE 100;
CREATE SEQUENCE gx_cs2;
CREATE SEQUENCE gx_cs3 START WITH 5 CACHE 20;
```

## ora2pg output (v25.0)

```sql
CREATE SEQUENCE gx_cs INCREMENT 1 NO MINVALUE NO MAXVALUE START ;
CREATE SEQUENCE gx_cs1 INCREMENT 1 NO MINVALUE NO MAXVALUE START  CACHE 100;
CREATE SEQUENCE gx_cs3 INCREMENT 1 NO MINVALUE NO MAXVALUE START 5 CACHE 20;
```

In file mode the START value is left empty - and with no option at all, `gx_cs2` loses its last digit and becomes `gx_cs`.

## Observed problem

Neither loads:

```
ERROR:  syntax error at or near ";"
ERROR:  syntax error at or near "CACHE"
```

Found in all four of utPLSQL's sequences (`create sequence ut_suite_cache_seq /* licence */ cache 100;`).

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16, Oracle 23ai.

## Verdict

**Gap confirmed, severity high, failure_stage deployment.** `--prepare` writes the START WITH Oracle implies (`prepare_oracle_sequence_start`); ora2pg then writes `START 1` and keeps the name, checked: the sequences return 1, 1 and 5, as in Oracle. A fix in the output could not get the cut name back, so the repair is in the source.

Implemented: `ora2pg_gap_report/detectors/sequence_without_start.py`.
