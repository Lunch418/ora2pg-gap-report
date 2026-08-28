*English | [Русский](verification-capability-matrix.ru.md)*

# Verification capability matrix

`--verify` (see the README, "Post-migration verification" section)
compares pre-migration findings (a `--save` snapshot) against what's
actually left in the already-generated `ora2pg` PostgreSQL code. For some
detectors this is a meaningful check. For others it isn't, not because
something's unimplemented, but because the question itself, "is this
still in the output," is a tautology for them: the construct is
guaranteed to never appear in the output on any migration, regardless of
whether someone fixed it by hand or not. `verification.py`'s docstring
explains this in detail; this is a table for each of the 67 gaps, so
nobody has to read the code just to answer "can this specific one be
verified."

## How to read the "mode" column

- **`verbatim`** — `ora2pg` copies the flagged Oracle construct into the
  output essentially unchanged (confirmed for each detector in its own
  `docs/research/gap-*.md`, the "ora2pg output" section). Re-running the
  detector against the generated file is a real check: if the pattern is
  gone, someone deliberately rewrote the code by hand. `--verify` gives
  `STILL_PRESENT` or `NOT_DETECTED` in this case.
- **`not_verifiable`** — `ora2pg` either drops the construct entirely, or
  rewrites it into something else (the keyword itself can never end up
  in the output, not because someone fixed the problem, but by
  construction), or flattens the surrounding structure badly enough that
  re-detection can't be trusted. `--verify` always reports
  `NOT_VERIFIABLE` here, not `NOT_DETECTED`, because `NOT_DETECTED` would
  be misleading: it would look like "problem solved," when it actually
  means "we physically can't see this in the output, regardless of
  whether the problem is solved or not."
- **`generated_only`** — the detector (`connect_by`, GAP-005) already
  only analyzes generated `ora2pg` code (`--check-connect-by`); there's
  no separate pre-migration Oracle-side finding for it, so `--verify` has
  nothing to compare against.

## Table

| GAP | Detector | Mode | Why |
|---|---|---|---|
| 001 | `autonomous_tx` | `not_verifiable` | The finding is about underestimated/missing cost in `SHOW_REPORT`/`--estimate_cost`, not about the shape of the code. There's nothing to compare in the generated output. |
| 002 | `merge_delete_clause` | `verbatim` | The construct is copied into the output unchanged. |
| 003 | `bulk_collect` | `verbatim` | The construct is copied into the output unchanged. |
| 004 | `compound_triggers` | `not_verifiable` | `COMPOUND TRIGGER` drops out of the file mode entirely, with no warning. |
| 005 | `connect_by` | `generated_only` | Already only analyzes generated code (`--check-connect-by`) — there's no pre-migration finding to compare against. |
| 006 | `database_link` | `verbatim` | The construct is copied into the output unchanged. |
| 007 | `model_clause` | `verbatim` | The construct is copied into the output unchanged. |
| 008 | `pivot_clause` | `verbatim` | The construct is copied into the output unchanged. |
| 009 | `object_type` | `verbatim` | The construct is copied into the output unchanged. |
| 010 | `with_function` | `not_verifiable` | The surrounding structure gets flattened badly enough that re-detection can't be trusted. |
| 011 | `flashback_query` | `verbatim` | The construct is copied into the output unchanged. |
| 012 | `global_temp_table` | `not_verifiable` | The `ON COMMIT` clause disappears entirely, without a trace. |
| 013 | `table_partitioning` | `not_verifiable` | `PARTITION BY` gets dropped entirely. |
| 014 | `connect_by_nocycle` | `not_verifiable` | The surrounding structure gets flattened badly enough that re-detection can't be trusted. |
| 015 | `context_object` | `not_verifiable` | The construct disappears from the output entirely, the only trace is a DEBUG log line. |
| 016 | `insert_all` | `verbatim` | The construct is copied into the output unchanged. |
| 017 | `json_table` | `verbatim` | The construct is copied into the output unchanged. |
| 018 | `external_table` | `not_verifiable` | The whole `ORGANIZATION EXTERNAL` clause gets dropped. |
| 019 | `sql_macro` | `not_verifiable` | The `SQL_MACRO` keyword is unconditionally dropped. |
| 020 | `invisible_column` | `not_verifiable` | The `INVISIBLE` modifier gets dropped. |
| 021 | `collection_type` | `not_verifiable` | `CREATE TYPE ... TABLE OF/VARRAY OF` never appears in the output at all, only a DEBUG log line. |
| 022 | `cross_apply` | `verbatim` | The construct is copied into the output unchanged. |
| 023 | `oracle_text` | `not_verifiable` | A mixed case: `INDEXTYPE` is dropped, `CONTAINS()`/similar are copied as-is — the whole detector is marked `not_verifiable` so a partial signal doesn't get passed off as a complete one. |
| 024 | `recursive_with` | `verbatim` | The construct is copied into the output unchanged. |
| 025 | `invisible_index` | `not_verifiable` | The `INVISIBLE` modifier disappears without a trace. |
| 026 | `read_only_table` | `not_verifiable` | `READ ONLY` gets dropped entirely. |
| 027 | `materialized_view_log` | `not_verifiable` | The construct disappears from the output entirely, the only trace is a DEBUG log line. |
| 028 | `identity_column` | `verbatim` | The construct is copied into the output unchanged. |
| 029 | `rowid_type` | `not_verifiable` | `ROWID`/`UROWID` gets rewritten to `oid` — the keyword itself is never preserved. |
| 030 | `sequence_cycle` | `not_verifiable` | The `CYCLE` keyword is unconditionally dropped. |
| 031 | `default_on_null` | `verbatim` | The `ON NULL` clause is copied into `CREATE TABLE` unchanged. |
| 032 | `public_synonym` | `not_verifiable` | Rewritten into a `CREATE VIEW`; `SYNONYM`/`FOR` are never preserved. |
| 033 | `virtual_column` | `not_verifiable` | Rewritten into a plain column + trigger; the original clause is never preserved. |
| 034 | `nested_subprogram` | `not_verifiable` | The nesting gets flattened; the structure can't be re-detected. |
| 035 | `conditional_compilation` | `verbatim` | The `$IF`/`$ELSIF`/`$ELSE`/`$END` directives are copied into the body unchanged. |
| 036 | `package_state` | `not_verifiable` | Rewritten into `set_config`/`current_setting`; the original declaration is never preserved. |
| 037 | `index_organized_table` | `not_verifiable` | The `ORGANIZATION INDEX` keyword is unconditionally dropped. |
| 038 | `match_recognize` | `verbatim` | The whole MATCH_RECOGNIZE(...) clause is copied into the output unchanged. |
| 039 | `connect_by_pseudocolumn` | `verbatim` | CONNECT_BY_ROOT/ISLEAF/ISCYCLE survive verbatim into the generated recursive CTE. |
| 040 | `keep_dense_rank` | `verbatim` | The KEEP (DENSE_RANK ...) modifier is copied into the output unchanged. |
| 041 | `multiset_operator` | `verbatim` | CAST(MULTISET(...)), MULTISET UNION, MEMBER OF, SUBMULTISET OF are all copied unchanged. |
| 042 | `sample_clause` | `verbatim` | SAMPLE (n) is copied into the output unchanged (never rewritten to TABLESAMPLE). |
| 043 | `accessible_by` | `verbatim` | The clause is copied verbatim into the generated function header. |
| 044 | `local_time_zone` | `not_verifiable` | Rewritten to a bare `timestamp`; the WITH LOCAL TIME ZONE keywords never survive. |
| 045 | `temporal_validity` | `not_verifiable` | Mangled into a bare `period FOR`; the named PERIOD FOR shape never survives. |
| 046 | `bitmap_index` | `not_verifiable` | Rewritten to CREATE INDEX ... USING gin; the BITMAP keyword never survives. |
| 047 | `object_table` | `not_verifiable` | `OF <type>` becomes a column named `of`; the object-table shape never survives. |
| 048 | `ignore_nulls` | `verbatim` | IGNORE/RESPECT NULLS is copied into the output unchanged. |
| 049 | `nlssort` | `not_verifiable` | Rewritten into a COLLATE clause; the NLSSORT call itself never survives. |
| 050 | `long_raw_type` | `not_verifiable` | Rewritten to `text`; the LONG RAW keyword never survives. |
| 051 | `anydata_type` | `verbatim` | The SYS.ANYDATA type name is carried into the output unchanged. |
| 052 | `system_trigger` | `verbatim` | The ON DATABASE/SCHEMA scope survives (lowercased) in the generated CREATE TRIGGER. |
| 053 | `trigger_follows` | `not_verifiable` | The clause does survive, but into the trigger *function's body* rather than the CREATE TRIGGER header this detector reads -- verbatim in the file, still not re-detectable. |
| 054 | `table_collection` | `verbatim` | The TABLE(...) operator is copied into the output unchanged. |
| 055 | `cursor_expression` | `verbatim` | CURSOR(SELECT ...) is copied into the output unchanged. |
| 056 | `for_update_wait` | `verbatim` | The WAIT n clause is copied into the output unchanged. |
| 057 | `rownum_dml` | `not_verifiable` | Rewritten to LIMIT n; the ROWNUM keyword never survives. |
| 058 | `to_date_rr` | `verbatim` | The RR format model is left in place inside TO_DATE. |
| 059 | `authid_clause` | `not_verifiable` | The whole routine is dropped, so nothing at all reaches the output to re-detect. |
| 060 | `pragma_exception_init` | `not_verifiable` | The pragma is dropped; only a placeholder SQLSTATE remains in the handler. |
| 061 | `subtype_range` | `not_verifiable` | Becomes CREATE DOMAIN; the SUBTYPE keyword never survives. |
| 062 | `alt_quote_literal` | `verbatim` | The q'...' literal is copied into the output unchanged. |
| 063 | `goto_statement` | `verbatim` | GOTO and its label are copied into the output unchanged. |
| 064 | `cursor_rowtype` | `not_verifiable` | %ROWTYPE survives, but `CURSOR c IS` becomes `c CURSOR FOR`, so the cursor name no longer resolves for this detector. |
| 065 | `wm_concat` | `verbatim` | The WM_CONCAT call is copied into the output unchanged (unlike LISTAGG). |
| 066 | `read_only_view` | `not_verifiable` | The WITH READ ONLY clause is dropped unconditionally. |
| 067 | `sdo_geometry` | `not_verifiable` | Rewritten to the PostGIS `geometry` type; the SDO_GEOMETRY name never survives. |

Totals among the 67 gaps themselves: 30 `verbatim`, 36 `not_verifiable`
(including `autonomous_tx`, but for a different reason, see above), 1
`generated_only` (`connect_by`).

Separate from the gap registry, but also in `VERIFICATION_MODE`:
`dbms_utl_calls` is a classifier for specific `DBMS_*`/`UTL_*` calls, not
a separately registered gap (it has no GAP-NNN number), so it isn't in
the table above. Mode: `verbatim` — the classified calls are copied into
the output unchanged.

This table and `ora2pg_gap_report/verification.py::VERIFICATION_MODE` are
one source of truth in intent: `scripts/doctor.py` checks that a mode is
set for every detector in the registry, but not that this table hasn't
drifted from the code line by line (a textual markdown description of
the reason can't be automatically cross-checked). When adding a new
detector, see `CONTRIBUTING.md`/`DEVELOPMENT.md` — the verification mode
is set alongside the detector itself, this table needs a manual update.
