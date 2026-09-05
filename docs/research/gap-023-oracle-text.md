# GAP-023: Oracle Text — the domain index is dropped and the search functions are not carried over

Oracle feature: Oracle Text — full-text search through a domain index
(`CREATE INDEX ... INDEXTYPE IS CTXSYS.CONTEXT`, also `CTXCAT`/`CTXRULE`)
and the `CONTAINS()`/`CATSEARCH()`/`MATCHES()` functions.

## Minimal example

```sql
CREATE TABLE articles (article_id NUMBER, body CLOB);

CREATE INDEX articles_body_idx ON articles(body)
INDEXTYPE IS CTXSYS.CONTEXT;
```

```sql
SELECT COUNT(*) INTO v_count
FROM articles
WHERE CONTAINS(body, 'oracle') > 0;
```

## ora2pg output (v25.0, `-t TABLE` and `-t PACKAGE`)

```sql
CREATE TABLE articles (
	article_id bigint,
	body text
) ;
CREATE INDEX articles_body_idx ON articles (body);
```

The `INDEXTYPE IS CTXSYS.CONTEXT` clause disappears without trace — the
index is converted as an ordinary B-tree. The `CONTAINS(body, 'oracle')`
call is copied as written.

## Observed problem

Creating the table and the index succeeds without error — but this is not
an ordinary table with an ordinary index: it is a table that has entirely
lost the full-text search capability the index existed for. A plain B-tree
over a `CLOB`/`text` column gives nothing resembling `CONTAINS()`.

Confirmed against a real PostgreSQL 16 — the `CONTAINS()` call fails on
the first invocation:

```
ERROR:  function contains(text, unknown) does not exist
HINT:  No function matches the given name and argument types.
```

PostgreSQL has an architectural equivalent — `tsvector`/`tsquery` plus a
GIN index (`to_tsvector(...)`/`@@`) — but it is a fundamentally different
syntax and model (language dictionaries, ranking via `ts_rank`), requiring
a manual rewrite rather than a syntactic substitution.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/oracle_text.py` — it covers both the domain
index itself (`INDEXTYPE IS CTXSYS.*`) and the search functions
(`CONTAINS`/`CATSEARCH`/`MATCHES`), since both ends of the same feature are
lost equally silently.
