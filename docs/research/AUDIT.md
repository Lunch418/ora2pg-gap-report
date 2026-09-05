# Registry audit: the evidence behind each confirmed gap

This document is not new research but a check on what is already
documented in [`GAP_REGISTRY.md`](GAP_REGISTRY.md): for every confirmed
gap it brings together, in one place, what specifically proves the gap
exists and what proves the corresponding detector has no false positives.

Audit criteria (applied once per GAP-NNN):

1. **Research document** — exists and contains a minimal reproducible
   example.
2. **Real ora2pg output** — not a "probably won't work" hypothesis but
   the literal output of `ora2pg -t ... -o ...` on that example.
3. **Expected vs Actual** — what should have come out in PostgreSQL and
   what actually did; for most gaps this is a literal error from a real
   PostgreSQL 16 when loading or calling the generated code.
4. **Detector** — a file in `ora2pg_gap_report/detectors/`, with an
   assigned severity.
5. **Regression tests** — how many tests there are and how many of them
   are guard tests against false positives (counted programmatically: a
   test is classified as a guard if it contains `== []` — "there must be
   no findings on this input" — rather than by the function's name).

The test counts in this document come from running a script over the
current test tree, not from counting by hand — see "How to re-check this
yourself" below.

## Summary table

| GAP | Detector | Sev | Doc §§ complete | ora2pg output | PG error/behaviour | Tests (total/guard) | Verified on real open-source code |
|---|---|---|---|---|---|---|---|
| 001 | `autonomous_tx` | high | ✅ | ✅ (`logger.pkb`, dblink wrapper) | n/a — this is a cost-estimation bug, not a syntax one | 16 / 3 (`test_autonomous_tx.py` + `test_autonomous_tx_edge_cases.py`) | yes — `test_real_open_source_utplsql_test_helper_is_attributed` embeds a real fragment of `main_helper.pkb`, and `test_real_open_source_utplsql_hidden_pragma_inside_dynamic_sql_is_found` a `PRAGMA` hidden inside dynamic SQL in `run_helper.pkb`, both from `utPLSQL` |
| 002 | `merge_delete_clause` | high | ✅ | ✅ | ✅ `ERROR: syntax error at or near "WHERE"` | 5 / 3 | no |
| 003 | `bulk_collect` | high | ✅ | ✅ | ✅ `ERROR: syntax error at or near "IS"` | 12 / 5 | yes — `test_local_collection_type_in_a_package_spec_is_attributed_not_unknown` (`amazon_aws_s3_pkg.pks`, `alexandria-plsql-utils`), `test_real_open_source_utplsql_bulk_collect_into_is_attributed` (`main_helper.pkb`, `utPLSQL`) and `test_real_open_source_utplsql_bulk_collect_hidden_inside_dynamic_sql_is_found` — a `BULK COLLECT INTO` hidden in dynamic SQL in `coverage_helper.pkb` (`utPLSQL`) |
| 004 | `compound_triggers` | high | ✅ | ✅ (`-- Nothing found of type TRIGGER`) | n/a — the trigger drops out of ora2pg's output entirely | 5 / 3 | no |
| 005 | `connect_by` | high | ✅ | ✅ (the generated `WITH RECURSIVE`) | ✅ `c.level` does not exist in the CTE | 11 / 3 | no (the detector analyses ora2pg's output, not source code — not applicable to scanning sources directly) |
| 006 | `database_link` | high | ✅ | ✅ | ✅ `ERROR: syntax error at or near "@"` | 5 / 3 | no |
| 007 | `model_clause` | high | ✅ | ✅ | ✅ `ERROR: syntax error at or near "PARTITION"` | 5 / 3 | no |
| 008 | `pivot_clause` | high | ✅ | ✅ | ✅ `ERROR: syntax error at or near "("` | 6 / 2 | no |
| 009 | `object_type` | high | ✅ | ✅ (`--estimate_cost` returned 0 rows) | n/a — a hole in the cost estimate, not in the syntax | 7 / 2 | yes — `test_real_open_source_object_type_is_flagged` (`t_soap_envelope.pks`, `alexandria-plsql-utils`) and `test_real_open_source_utplsql_object_types_are_flagged` (`demo_equal_matcher.sql`, `utPLSQL`) |
| 010 | `with_function` | high | ✅ | ✅ | ✅ `ERROR: syntax error at end of input` (the block structure is destroyed) | 4 / 1 | yes — `test_real_open_source_excelgen_with_function_is_flagged` embeds a real `WITH FUNCTION get_xlsx(...)` from the `mbleron/ExcelGen` test suite |
| 011 | `flashback_query` | high | ✅ | ✅ (a mangled `statement_timestamp()`) | ✅ `ERROR: syntax error at or near "timestamp"` | 4 / 1 | no |
| 012 | `global_temp_table` | high | ✅ | ✅ | ✅ the row survived `COMMIT`, contrary to Oracle semantics | 6 / 2 | yes — `test_real_open_source_utplsql_global_temp_table_is_flagged` embeds the real `ut_compound_data_diff_tmp` table from `utPLSQL` |
| 013 | `table_partitioning` | high | ✅ | ✅ | n/a — the clauses vanish silently, no error | 10 / 4 | yes — `test_real_oracle_sample_schema_sales_table_is_flagged` embeds the real `SALES` table from Oracle's official SH schema (`db-sample-schemas`) |
| 014 | `connect_by_nocycle` | high | ✅ | ✅ (`WITH RECURSIVE` placed before `DECLARE`) | ✅ `ERROR` at body-compilation time | 4 / 1 | no |
| 015 | `context_object` | medium | ✅ | ✅ (only a DEBUG line in the log) | n/a — the construct vanishes without a trace | 3 / 1 | no |
| 016 | `insert_all` | high | ✅ | ✅ | ✅ `ERROR: "big_orders" is not a known variable` | 5 / 2 | no |
| 017 | `json_table` | high | ✅ | ✅ | ✅ `ERROR: syntax error at or near "COLUMNS"` | 5 / 3 | yes — `test_json_table_inside_a_view_is_attributed_not_unknown` (in `tests/test_cli.py`) embeds the real `product_reviews` view from `db-sample-schemas` |
| 018 | `external_table` | high | ✅ | ✅ | n/a — the clause vanishes, the table is created empty | 4 / 1 | no |
| 019 | `sql_macro` | high | ✅ | ✅ | ✅ `ERROR: argument of WHERE must be type boolean` | 3 / 1 | no |
| 020 | `invisible_column` | high | ✅ | ✅ | ✅ the column showed up in `SELECT *`, contrary to Oracle semantics | 8 / 2 | no |
| 021 | `collection_type` | high | ✅ | ✅ (`[DEBUG] unhandled line`) | ✅ `ERROR: type "phone_list_t" does not exist` | 8 / 3 | yes — `test_real_open_source_utplsql_collection_type_is_flagged` embeds the real `demo_departments` type from `utPLSQL` |
| 022 | `cross_apply` | high | ✅ | ✅ | ✅ `ERROR: syntax error at or near "APPLY"` | 3 / 1 | no |
| 023 | `oracle_text` | high | ✅ | ✅ | ✅ `ERROR: function contains(text, unknown) does not exist` | 12 / 4 | yes — `test_real_oracle_sample_schema_index_is_flagged` embeds the real `sup_text_idx` index from Oracle's official SH schema (`db-sample-schemas`) |
| 024 | `recursive_with` | high | ✅ | ✅ | ✅ `ERROR: relation "tree" does not exist` (`WITH RECURSIVE` is required) | 8 / 5 | no |
| 025 | `invisible_index` | medium | ✅ | ✅ | n/a — the optimizer silently starts considering the index | 8 / 3 | no |
| 026 | `read_only_table` | high | ✅ | ✅ | ✅ an INSERT succeeded where Oracle blocks it outright (ORA-12081) | 7 / 3 | no |
| 027 | `materialized_view_log` | high | ✅ | ✅ (`[DEBUG] unhandled line`) | n/a — the log vanishes without a trace | 3 / 2 | no |
| 028 | `identity_column` | high | ✅ | ✅ (an extra pair of parentheses in the output) | ✅ `ERROR: syntax error at or near "("` | 5 / 2 | no |
| 029 | `rowid_type` | high | ✅ | ✅ (`ROWID`/`UROWID` → `oid`) | ✅ `ERROR: invalid input syntax for type oid` when inserting a real value | 11 / 4 | no |
| 030 | `sequence_cycle` | high | ✅ | ✅ (the `CYCLE` clause vanishes) | ✅ `ERROR: nextval: reached maximum value of sequence` once the range is exhausted | 6 / 2 | no |
| 031 | `default_on_null` | high | ✅ | ✅ (`ON NULL` copied as-is) | ✅ `ERROR: syntax error at or near "ON"`, already at CREATE TABLE | 7 / 2 | no |
| 032 | `public_synonym` | high | ✅ | ✅ (rewritten as a `CREATE VIEW` without the schema) | ✅ `ERROR: relation ... does not exist` when names collide | 8 / 1 | no |
| 033 | `virtual_column` | medium | ✅ | ✅ (rewritten as a column + trigger) | n/a — the value is correct, only the protection against explicit assignment is lost | 8 / 4 | no |
| 034 | `nested_subprogram` | high | ✅ | ✅ (the body is mangled, the nesting flattened) | ✅ `ERROR: syntax error at or near "BEGIN"` on the first call | 9 / 3 | yes — `test_real_open_source_logger_nested_procedure_inside_conditional_compilation_is_flagged` (`get_cgi_env`/`append_cgi_env`, `Logger`; scanning the full file really does find 5 such pairs) |
| 035 | `conditional_compilation` | high | ✅ | ✅ (`$IF`/`$THEN`/`$ELSE`/`$END` copied as-is) | ✅ `ERROR: syntax error at or near "$"` on the first call | 6 / 2 | yes — `test_real_open_source_logger_assert_procedure_is_flagged` (`assert`, `Logger`; scanning the full file really does find 229 such directives) |
| 036 | `package_state` | high | ✅ | ✅ (`set_config`/`current_setting` without a cast or `missing_ok`) | ✅ `ERROR: function set_config(unknown, bigint, boolean) does not exist` | 13 / 4 | yes — `test_real_open_source_logger_package_variables_are_flagged` (`g_log_id`/`g_running_timers`/`g_in_plugin_error`, `Logger`) |
| 037 | `index_organized_table` | medium | ✅ | ✅ (rewritten as a heap + a separate index) | n/a — the integrity constraints are preserved, only the storage architecture is lost | 7 / 3 | no |
| 038 | `match_recognize` | high | ✅ | ✅ (copied verbatim) | ✅ `ERROR: syntax error at or near "BY"` at load | 4 / 2 | no |
| 039 | `connect_by_pseudocolumn` | high | ✅ | ✅ (`CONNECT_BY_ROOT`/`ISLEAF`/`ISCYCLE` carried verbatim into the generated CTE) | ✅ `ERROR: syntax error at or near "AS"` / `column "connect_by_iscycle" does not exist` | 4 / 2 | no |
| 040 | `keep_dense_rank` | high | ✅ | ✅ (copied verbatim) | ✅ `ERROR: syntax error at or near "("` | 4 / 2 | no |
| 041 | `multiset_operator` | high | ✅ | ✅ (all four forms copied verbatim) | ✅ `ERROR: syntax error at or near "col_b"` / `"SELECT"` / `"SUBMULTISET"` | 5 / 1 | yes — `test_real_utplsql_multiset_union_all_is_flagged` (`ut_suite_builder.pkb`, `utPLSQL`; a full corpus scan yields 52 findings) |
| 042 | `sample_clause` | high | ✅ | ✅ (copied verbatim, not rewritten into `TABLESAMPLE`) | ✅ `ERROR: syntax error at or near "10"` | 4 / 2 | no |
| 043 | `accessible_by` | high | ✅ | ✅ (copied into the generated function's header) | ✅ `ERROR: syntax error at or near "ACCESSIBLE"` | 4 / 2 | no |
| 044 | `local_time_zone` | high | ✅ | ✅ (`ts_ltz timestamp` — without a time zone) | n/a — there is never an error; verified on a live PG that the conversion into the session's TZ disappears | 5 / 2 | yes — `test_real_oracle_sample_schema_orders_table_is_flagged` (`order_entry/cord_v3.sql`, `db-sample-schemas`) |
| 045 | `temporal_validity` | high | ✅ | ✅ (a `period FOR` stub in the column list) | ✅ `ERROR: syntax error at or near "FOR"` | 4 / 2 | no |
| 046 | `bitmap_index` | high | ✅ | ✅ (`CREATE INDEX ... USING gin(...)`) | ✅ `ERROR: data type character varying has no default operator class for access method "gin"` | 5 / 1 | yes — `test_real_oracle_sample_schema_star_schema_bitmap_indexes_are_flagged` (`sales_history/sh_populate.sql`, `db-sample-schemas`; 15 findings when scanned) |
| 047 | `object_table` | high | ✅ | ✅ (`OF` becomes a column name, the PK is lost) | n/a — when the type exists the load goes through silently and the table is structurally wrong | 6 / 2 | yes — `test_real_utplsql_object_table_line_points_at_the_of_keyword_not_create_table` (`ut_suite_cache.sql`, `utPLSQL`) and `categories_tab` from `db-sample-schemas` |

**47/47 on each of the first five criteria.** The separate column is
verification against real open-source code: 9 detectors (`autonomous_tx`,
`bulk_collect`, `object_type`, `global_temp_table`, `table_partitioning`,
`json_table`, `collection_type`, `oracle_text`, `with_function`) actually
fired while scanning 247,298 lines of open-source code (an exact fresh
count across all seven repositories together at the time of this audit,
each a fresh `git clone --depth 1`, not a sum of separately remembered
per-repository numbers) from seven independent projects —
`mortenbra/alexandria-plsql-utils`, `oracle-samples/db-sample-schemas`,
`utPLSQL/utPLSQL` (a PL/SQL unit-testing framework),
`OraOpenSource/Logger`, `method5/plsql_lexer` (a PL/SQL
lexer/tokenizer — with the non-standard file extensions
`.plsql`/`.bdy`/`.spc` passed explicitly, not through a recursive
directory walk by extension), `mbleron/ExcelGen` (an Excel file
generator) and `osalvador/tePLSQL` (a templating engine that leans
heavily on `EXECUTE IMMEDIATE`) — and for each of those nine there is a
permanent regression test in the test tree embedding a real fragment of
that very source (not a hypothetical example), so the finding stays
verifiable at any time rather than being "spotted once in a session".
Growing the corpus from four projects to seven produced no incorrect
findings and no crashes — including two files (`ExcelGen.pkb`,
`plsql_parser.bdy`) where `EXECUTE IMMEDIATE` really does build code
dynamically (down to creating a temporary function with the schema name
substituted into a template) without once provoking a false attribution:
none of those dynamically created objects entered the container index as
a real one (in those two specific cases the dynamic code happened to
contain no detector's target construct at all — which confirms the
absence of crashes and data corruption, and adds no new finding). From
the earlier expansion (two projects → four) there remains an already
documented, honest limit of applicability — `object_name='UNKNOWN'` on an
anonymous `declare...begin...end;` block with no name (an install script,
not a `DBMS_METADATA.GET_DDL` export), pinned by the test
`test_real_open_source_logger_install_script_anonymous_block_is_unknown_not_a_crash`
in `tests/test_bulk_collect.py`.

Separately from the corpus expansion: the 14 detectors that use the
shared attribution index (`bulk_collect`, `connect_by_nocycle`,
`cross_apply`, `database_link`, `flashback_query`, `insert_all`,
`json_table`, `merge_delete_clause`, `model_clause`, `oracle_text`,
`pivot_clause`, `recursive_with`, `sql_macro`, `with_function`), plus
`autonomous_tx` separately, now see their target construct even when it
is built dynamically inside `EXECUTE IMMEDIATE` — and on this same corpus
exactly two new real cases turned up and were confirmed: a hidden `PRAGMA
AUTONOMOUS_TRANSACTION` and a hidden `BULK COLLECT INTO`, both in
`utPLSQL`, both correctly attributed to a real procedure in the static
source tree (not to an imaginary object that exists only at execution
time) — see the "Constructs hidden in dynamic SQL" section of
`docs/ARCHITECTURE.md` for the design, and
`tests/test_plsql_lex.py`/`tests/test_autonomous_tx.py`/
`tests/test_bulk_collect.py` for the regression tests on the real
fragments.

The remaining detectors did not meet their target construct in any of
these seven corpora — as expected: some of these constructs (`SQL_MACRO`,
`CREATE CONTEXT`, `INVISIBLE` columns and indexes, `ORGANIZATION
EXTERNAL`, `CONNECT BY NOCYCLE`, `CROSS APPLY`, a natively recursive
`WITH` without `RECURSIVE`, `READ ONLY` tables, `MATERIALIZED VIEW LOG`,
`IDENTITY` with options) are rare, specialised Oracle features that are
statistically unlikely to appear even across seven open-source projects.
For those, "proof of no false positives" means targeted unit tests on
known collision scenarios (partitioned outer join, window functions,
GRANT lists, comments/strings, nested local declarations and so on),
rather than statistics over a large corpus.

## What "Doc §§ complete" means for GAP-001/004/005

These three documents use a different heading structure (`## What is
actually wrong here` instead of separate `## Minimal example` / `##
ora2pg output`) — they were written earlier, before the current template
settled. In substance they contain all the same things (a minimal
example, real ora2pg output, `Reproducible: YES`, the ora2pg version, a
verdict) — verified by reading them line by line while preparing this
audit, not by an automatic check on heading names.

## How to re-check this yourself

```sh
pytest -v                                    # see the exact number below
ruff check ora2pg_gap_report/ tests/          # no findings
python3 scripts/audit_gap_test_counts.py      # recompute the "Tests (total/guard)" column of the table above
```

As of the last update of this document: **387 tests** (386 pass, 1
deliberately skipped — it needs `ora2pg` installed, see
`--check-connect-by`). The "Tests (total/guard)" column in the table
above is not a manual count but the literal output of
`scripts/audit_gap_test_counts.py` at the time this file was last
updated; when new tests are added it is enough to re-run the script and
update the table with its output.

A live re-check of a specific gap against a real PostgreSQL follows the
steps of that gap's own `docs/research/gap-NNN-*.md`: the `ora2pg`
command, its output, then `psql -f` and `CALL`/`SELECT`, with exactly the
results documented there (`ora2pg` 25.0 and PostgreSQL 16 were used
throughout this registry).


## Corpus verification for GAP-038..047

The GAP-038..047 batch was checked in a separate run over **3 of the 7**
corpus repositories (`utPLSQL/utPLSQL`,
`mortenbra/alexandria-plsql-utils`, `oracle-samples/db-sample-schemas`),
each a fresh `git clone --depth 1` — **209,793 lines**, 511 files. This
is deliberately narrower coverage than the full 247,298 lines across
seven repositories above: the other four were not part of this run, and
recording it as equivalent to the full one would be wrong.

Result: **0 crashes**; 4 of the 10 new detectors fired, and every finding
was inspected by eye and turned out to be a real construct, not a false
positive:

| Detector | Findings | Where |
|---|---|---|
| `multiset_operator` | 52 | `utPLSQL` — makes heavy use of collections |
| `bitmap_index` | 15 | `db-sample-schemas/sales_history` — the textbook star schema |
| `object_table` | 2 | `utPLSQL/ut_suite_cache.sql`, `db-sample-schemas/oc_cre.sql` |
| `local_time_zone` | 1 | `db-sample-schemas/order_entry/cord_v3.sql` |

The run additionally uncovered a real attribution bug the synthetic tests
had missed: `object_table` pointed at the `CREATE TABLE` line instead of
the line of the `OF` itself when a comment sits between them (in
`ut_suite_cache.sql` — a 13-line licence header). Fixed, with a
regression test built on that same real shape.


## The GAP-048..067 batch (second wave)

The same method and the same rig: real `ora2pg 25.0` + real PostgreSQL
16, with a minimal Oracle example per candidate, an `ora2pg` run, and a
load of the generated output into a live database. Every gap has its own
research document with the actual output of both commands.

It is worth recording separately what was **rejected** — so the registry
does not look as though everything gets confirmed. Tested and found to
convert correctly (that is, not a gap):

| Candidate | What the run showed |
|---|---|
| `(+)` — the old outer-join syntax | correctly rewritten into `LEFT OUTER JOIN`, and it runs |
| `ORDER SIBLINGS BY` | correctly rewritten into a recursive CTE with a hierarchy array; sibling order on real data is right |
| `SYS_GUID()` | correct, and ora2pg even emits `CREATE EXTENSION "uuid-ossp"` itself |
| `NUMTODSINTERVAL` / `NUMTOYMINTERVAL` | correct, the resulting values are right |
| `SELECT UNIQUE` | correctly rewritten into `SELECT DISTINCT` |
| `SYS_REFCURSOR` | correctly rewritten into `REFCURSOR` |
| `NOCOPY` | dropped, but it is only a hint to the compiler — behaviour does not change |
| `LONG` (the character one) | correctly mapped to `text` |
| `INTERVAL YEAR TO MONTH` / `DAY TO SECOND` | mapped to `interval`; showed no observable divergence |
| `ENABLE ROW MOVEMENT`, `ROW ARCHIVAL`, a sequence's `SCALE`/`ORDER` | the clauses are dropped; showed no observable failure or divergence |
| `FORALL ... SAVE EXCEPTIONS` | a real gap, but already covered by GAP-003 (`bulk_collect` catches `FORALL`) |
| `VARRAY` / a nested table in a type declaration | a real gap, but already covered by GAP-021 (`collection_type`) |

None of the 20 confirmed candidates overlaps the 47 existing detectors —
verified by running the current scanner over all the example sources
before implementing anything (all 20 returned `NONE`).

### A second corpus run

All 20 new detectors were run over real open-source Oracle code:
`utPLSQL`, `alexandria-plsql-utils`, `db-sample-schemas`, `Logger` —
**766 files, 229,787 lines, 0 crashes**. 12 of the 20 detectors fired;
every finding was inspected by eye against the sources and turned out to
be a real construct:

| Detector | Findings | Where |
|---|---|---|
| `alt_quote_literal` | 706 | `utPLSQL` — `q'[...]'` is used everywhere |
| `table_collection` | 267 | `utPLSQL`, `alexandria` — `from table(...)` |
| `to_date_rr` | 211 | `db-sample-schemas/order_entry` — `'DD-MON-RR HH.MI.SS.FF AM'` in INSERTs |
| `authid_clause` | 50 | `utPLSQL` — nearly every package spec |
| `pragma_exception_init` | 44 | `utPLSQL`, `Logger` |
| `goto_statement` | 3 | `alexandria/csv_util_pkg.pkb` |
| `cursor_rowtype` | 2 | `utPLSQL/ut_suite_manager.pkb` |
| `subtype_range` | 2 | `utPLSQL/ut_utils.pks` |
| `sdo_geometry` | 2 | `db-sample-schemas/order_entry` |
| `system_trigger` | 1 | `utPLSQL/ut_trigger_annotation_parsing.trg` |
| `cursor_expression` | 1 | `alexandria/demos/string_util_pkg_demo.sql` |
| `read_only_view` | 1 | `db-sample-schemas/human_resources/hr_create.sql` |

For nine of them the regression tests are built directly on these real
shapes (rather than on synthetic ones), including the multi-line
`TO_TIMESTAMP` from `pord_v3.sql`, where the format string sits on the
line after the value.

Two results are worth singling out:

- **`authid_clause` on `utPLSQL`.** 50 findings — that is practically the
  project's entire public API. ora2pg drops every such package from its
  output entirely, and silently. For a project of that size it means
  almost nothing of the schema survives the conversion, and the only way
  to find out is after the fact.
- **`to_date_rr` on Oracle's own samples.** 211 findings in
  `db-sample-schemas` — these are INSERTs with dates. They will load
  without a single error and yield the year 1 BC.

Eight detectors did not fire on the corpus (`anydata_type`,
`for_update_wait`, `ignore_nulls`, `long_raw_type`, `nlssort`,
`rownum_dml`, `trigger_follows`, `wm_concat`). That is not a sign they
are unnecessary and not a reason to remove them: each is confirmed by a
real `ora2pg` + PostgreSQL run in its own research document; these
constructs simply do not appear in those four particular open-source
projects. It is recorded here explicitly so as not to leave the
impression that the corpus confirms all twenty.

### Checking the recommendations themselves

A separate pass checked what usually goes unchecked: not "is there a
gap", but **does the advice we give for each gap actually work**. Every
recommended fragment was executed on a real PostgreSQL 16.

The pass was not a formality — it found a genuine error in text that had
already been written, in GAP-058. It said `RR` could be replaced with
`YY` because "PostgreSQL has the same rule". The rule is different:

| Range | Oracle `RR` | PostgreSQL `YY` |
|---|---|---|
| 00-49 | 20xx | 20xx |
| 50-69 | 19xx | **20xx** |
| 70-99 | 19xx | 19xx |

That is, the advice traded a loud breakage (the year 1 BC on every row)
for a quiet one — on a subset of the data, exactly in the range of birth
dates and mid-20th-century records. Fixed everywhere (the detector's
message, both variants of the short hint, the English translation, the
research document), with a guard test added so the wording cannot come
back.

The remaining recommendations were executed and work as stated:

| Gap | What was checked | Result |
|---|---|---|
| 049 | whether the recommended collation name exists | `de-DE-x-icu` is there; the text notes that `de_DE.utf8` "depends on the build having ICU" |
| 051 | the error text for the short spelling | exactly `type "anydata" does not exist`, as recorded in the document |
| 052 | `CREATE EVENT TRIGGER ... ON ddl_command_end` | is created and fires on DDL |
| 053 | "triggers fire in alphabetical order of their names" | confirmed: `t10_first` ran before `t20_second` even though it was created later — so the advice about naming really does work |
| 056 | `SET LOCAL lock_timeout = '5 s'` | accepted, the value is visible in `SHOW` |
| 061 | `CREATE DOMAIN ... CHECK (VALUE BETWEEN 1 AND 100)` | is created, the value is coerced |
| 062 | `$q$it's a test$q$` | works, nothing needs escaping |
| 064 | `RECORD` instead of `<cursor>%ROWTYPE` | a `FETCH` into a `RECORD` from a cursor works |
| 065 | `string_agg(col, ',' ORDER BY col)` | works, the order is deterministic |
| 066 | `REVOKE INSERT ON <view>` | writes really are blocked: `permission denied for view` |

The only thing not checked on the rig is `CREATE EXTENSION postgis`
(GAP-067) — PostGIS is not installed in this environment, and the
document says so directly rather than passing it off as verified.
