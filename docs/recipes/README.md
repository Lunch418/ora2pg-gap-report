*English | [Русский](README.ru.md)*

# Migration recipes

The [research docs](../research/GAP_REGISTRY.md) say what `ora2pg` gets
wrong and how we know. A recipe says what to write instead: for a class of
problem, the PostgreSQL pattern, with code that runs.

| Recipe | Gaps |
|---|---|
| [Hierarchical queries: CONNECT BY -> WITH RECURSIVE](hierarchical-queries.md) | GAP-005, 014, 024, 039 |
| [Collections and bulk operations](collections-and-bulk.md) | GAP-003, 021, 041, 054 |
| [Autonomous transactions](autonomous-transactions.md) | GAP-001 |
| [Package variables and application contexts](package-state.md) | GAP-015, 036 |
| [Global temporary tables](temporary-tables.md) | GAP-012, 111 |
| [PIVOT and UNPIVOT](pivot-unpivot.md) | GAP-008 |
| [INSERT ALL, MERGE ... DELETE and upserts](multi-table-dml.md) | GAP-002, 016, 070, 076, 077 |
| [Errors: raising, catching and naming them](error-handling.md) | GAP-060, 071, 084, 093, 094 |
| [Database links -> postgres_fdw](database-links.md) | GAP-006 |
| [DBMS_* and UTL_* calls](builtin-packages.md) | `dbms_utl_calls` |
| [KEEP, IGNORE NULLS, WM_CONCAT and SAMPLE](analytic-functions.md) | GAP-040, 042, 048, 065 |
| [Read-only tables and views, invisible columns and indexes](read-only-and-invisible.md) | GAP-020, 025, 026, 066 |
| [Partitioned tables](partitioning.md) | GAP-013 |
| [T-SQL expressions](tsql-expressions.md) | GAP-095, 096, 097, 098, 099 |
| [MySQL expressions](mysql-expressions.md) | GAP-068, 069, 075, 079, 081, 086 |

`ora2pg-gap-report --explain GAP-NNN` and the reports link to the recipe
for each gap that has one.

## How the code is checked

Every ` ```sql ` block in a recipe is PostgreSQL meant to run as written.
`tests/test_recipes.py` loads each page's blocks, in order, into a real
PostgreSQL 16 through `--load-check`, and the `DO ... ASSERT` blocks in the
pages check that each pattern does what the page says. A recipe that stops
working fails the build. Code shown only to read, such as the Oracle
original or a statement that needs a second database, is fenced as
` ```plsql ` or ` ```pgsql ` and is not run.

A recipe for a class not listed here is welcome: the same structure (the
problem, the pattern, what does not carry over) and code that passes the
test. See [CONTRIBUTING](../../CONTRIBUTING.md).
