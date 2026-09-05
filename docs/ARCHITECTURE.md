*English | [Русский](ARCHITECTURE.ru.md)*

# Architecture

This document covers how the tool is built internally: the lexer,
masking, finding attribution, dynamic SQL handling, file layout. For
"what this is and why," see [README.md](../README.md); for "how to
develop/test," see [DEVELOPMENT.md](DEVELOPMENT.md).

`ora2pg SHOW_REPORT` has no offline mode at all, it requires a live
connection to Oracle (`ORACLE_DSN`). Offline analysis from a DDL dump only
covers *individual object types* (`-t PACKAGE`, `-t TRIGGER`, `-t
FUNCTION`, …), which is exactly how `ora2pg_wrapper.py` works, not
through `SHOW_REPORT`. This is a hard requirement for the target
audience: closed networks, air-gapped environments, the public sector.

There are 106 detectors right now (the full table is in README.md,
"Detectors"; 105 of them are tied to a registered GAP-NNN,
`dbms_utl_calls` isn't, see README.md, "Why almost everything is high"),
split across three source dialects: 67 Oracle, 19 MySQL/MariaDB
(`ora2pg -m`) and 19 T-SQL/SQL Server (`ora2pg -M`). Each dialect has its
own lexer (`plsql_lex.py`, `mysql_lex.py`, `mssql_lex.py`) and its own
detector tuple in `core.py`, kept structurally separate so a file scanned
under the wrong `--dialect` cannot trigger another dialect's detectors.
Almost all of them work the same way: they analyze the source directly and
don't need `ora2pg` installed, plain Python, no external dependencies. There's
exactly one exception, `connect_by`: it's built differently, it lints
*generated* ora2pg code rather than the source (ora2pg handles CONNECT BY
reasonably well on its own, the value here isn't detection but checking
conversion quality), so it needs a real `ora2pg` and is only wired in via
`--check-connect-by`. It's the only detector with that requirement, not
"one of four" like the README's earliest versions said, back when there
really were only four detectors.

## File layout

```
pyproject.toml                 # single source of truth for dependencies/entry points
ora2pg_gap_report/
├── models.py                  # Finding -- the shared finding structure for every detector
├── detector_spec.py            # DetectorSpec + build(): the five scanning strategies the
│                               # declarative detectors are made of (see DEVELOPMENT.md)
├── messages.py                 # every finding's ru/en text, keyed by message id
├── lex_common.py               # the lexer parts no dialect changes -- line_at, balanced
│                               # parens, column-list spans -- plus the Lexer protocol
│                               # build() type-checks a dialect lexer against
├── plsql_lex.py                # shared infrastructure: string/comment masking (including
│                               # q-quotes) in two flavors -- safe, and with the EXECUTE
│                               # IMMEDIATE argument left visible -- BEGIN/CASE/IF/LOOP...END
│                               # block matching, identifier parsing -- used by every detector
├── oracle_connector.py         # live schema export (13 object types) via DBMS_METADATA.GET_DDL
├── oracle_export.py            # the ora2pg-gap-export console command
├── detectors/
│   ├── autonomous_tx.py           # PRAGMA AUTONOMOUS_TRANSACTION inside a PACKAGE BODY
│   ├── compound_triggers.py       # COMPOUND TRIGGER -- ora2pg's parser silently fails on it
│   ├── dbms_utl_calls.py          # classifier for specific DBMS_*/UTL_* functions
│   ├── connect_by.py              # lints the generated WITH RECURSIVE (needs ora2pg)
│   ├── merge_delete_clause.py     # MERGE ... DELETE WHERE -- no equivalent in PostgreSQL's MERGE
│   ├── bulk_collect.py            # TYPE ... IS TABLE OF / BULK COLLECT INTO / FORALL
│   ├── database_link.py           # table@dblink_name -- a direct reference to a remote DB
│   ├── model_clause.py            # MODEL PARTITION BY / DIMENSION BY / MEASURES / RULES
│   ├── pivot_clause.py            # PIVOT / UNPIVOT
│   ├── object_type.py             # CREATE TYPE ... AS OBJECT / TYPE BODY
│   ├── with_function.py           # WITH FUNCTION / WITH PROCEDURE
│   ├── flashback_query.py         # AS OF TIMESTAMP / AS OF SCN
│   ├── global_temp_table.py       # CREATE GLOBAL TEMPORARY TABLE -- ON COMMIT gets lost
│   ├── table_partitioning.py      # PARTITION BY RANGE/LIST/HASH -- dropped entirely
│   ├── connect_by_nocycle.py      # CONNECT BY NOCYCLE / ORDER SIBLINGS BY
│   ├── context_object.py          # CREATE CONTEXT -- an application context
│   ├── insert_all.py              # INSERT ALL / INSERT FIRST -- multi-table insert
│   ├── json_table.py              # JSON_TABLE(...) -- not in PostgreSQL 16 or older
│   ├── external_table.py          # CREATE TABLE ... ORGANIZATION EXTERNAL
│   ├── sql_macro.py               # SQL_MACRO -- converted into a plain function
│   ├── invisible_column.py        # an INVISIBLE column loses its invisibility
│   ├── collection_type.py         # CREATE TYPE ... TABLE OF / VARRAY OF
│   ├── cross_apply.py             # CROSS APPLY / OUTER APPLY
│   ├── oracle_text.py             # Oracle Text -- INDEXTYPE / CONTAINS / CATSEARCH / MATCHES
│   ├── recursive_with.py          # a recursive WITH with no RECURSIVE keyword
│   ├── invisible_index.py         # an INVISIBLE index
│   ├── read_only_table.py         # CREATE TABLE ... READ ONLY
│   ├── materialized_view_log.py   # CREATE MATERIALIZED VIEW LOG
│   ├── identity_column.py         # GENERATED ... AS IDENTITY (...) -- double-paren bug
│   ├── rowid_type.py              # ROWID/UROWID as a column type -- converted to oid
│   ├── sequence_cycle.py          # CREATE SEQUENCE ... CYCLE -- the clause gets dropped
│   ├── default_on_null.py         # DEFAULT ... ON NULL -- copied verbatim, a syntax error
│   ├── public_synonym.py          # CREATE [PUBLIC] SYNONYM -- loses the target object's schema
│   ├── virtual_column.py          # GENERATED ALWAYS AS (...) VIRTUAL -- loses ORA-54016 protection
│   ├── nested_subprogram.py       # a local nested procedure/function -- broken on export
│   ├── conditional_compilation.py # $IF/$ELSIF/$ELSE/$END -- copied verbatim
│   ├── package_state.py           # a package variable -- broken emulation via set_config
│   ├── index_organized_table.py   # ORGANIZATION INDEX (IOT) -- dropped entirely
│   ├── match_recognize.py         # MATCH_RECOGNIZE -- row pattern matching, no PG equivalent
│   ├── connect_by_pseudocolumn.py # CONNECT_BY_ROOT/ISLEAF/ISCYCLE -- carried through unconverted
│   ├── keep_dense_rank.py         # KEEP (DENSE_RANK FIRST/LAST ORDER BY ...) aggregate modifier
│   ├── multiset_operator.py       # CAST(MULTISET(...)), MULTISET UNION, MEMBER OF, SUBMULTISET OF
│   ├── sample_clause.py           # SAMPLE (n) -- PG spells it TABLESAMPLE, ora2pg doesn't convert
│   ├── accessible_by.py           # ACCESSIBLE BY -- copied into the generated function header
│   ├── local_time_zone.py         # TIMESTAMP WITH LOCAL TIME ZONE -- becomes a bare timestamp
│   ├── temporal_validity.py       # PERIOD FOR -- mangled into a truncated `period FOR`
│   ├── bitmap_index.py            # CREATE BITMAP INDEX -- becomes USING gin, no operator class
│   ├── object_table.py            # CREATE TABLE ... OF <type> -- OF becomes a column name
│   ├── ignore_nulls.py            # IGNORE/RESPECT NULLS -- no such syntax in PostgreSQL 16
│   ├── nlssort.py                 # NLSSORT -- becomes COLLATE with a nonexistent collation name
│   ├── long_raw_type.py           # LONG RAW -- mapped to text, not the documented bytea
│   ├── anydata_type.py            # SYS.ANYDATA -- type name copied through, SYS schema absent
│   ├── system_trigger.py          # ON DATABASE/SCHEMA triggers -- emitted as table triggers
│   ├── trigger_follows.py         # FOLLOWS/PRECEDES -- leaks into the trigger function body
│   ├── table_collection.py        # TABLE(...) collection unnesting -- copied verbatim
│   ├── cursor_expression.py       # CURSOR(SELECT ...) -- copied verbatim, no equivalent
│   ├── for_update_wait.py         # FOR UPDATE ... WAIT n -- only NOWAIT/SKIP LOCKED exist
│   ├── rownum_dml.py              # ROWNUM in UPDATE/DELETE -- becomes an illegal LIMIT
│   ├── to_date_rr.py              # RR format in TO_DATE -- silently yields year 1 BC
│   ├── authid_clause.py           # AUTHID -- the whole routine is silently dropped
│   ├── pragma_exception_init.py   # PRAGMA EXCEPTION_INIT -- handler gets a placeholder SQLSTATE
│   ├── subtype_range.py           # SUBTYPE ... RANGE -- copied into CREATE DOMAIN verbatim
│   ├── alt_quote_literal.py       # q'[...]' alternative quoting -- copied verbatim
│   ├── goto_statement.py          # GOTO -- PL/pgSQL has no such statement
│   ├── cursor_rowtype.py          # <cursor>%ROWTYPE -- PL/pgSQL allows only table/view
│   ├── wm_concat.py               # WM_CONCAT -- copied verbatim, unlike LISTAGG
│   ├── read_only_view.py          # WITH READ ONLY -- dropped, view becomes auto-updatable
│   ├── sdo_geometry.py            # SDO_GEOMETRY -- PostGIS type without CREATE EXTENSION
│   │                             # -- MySQL/MariaDB dialect (ora2pg -m; see mysql_lex.py) --
│   ├── mysql_enum_type.py         # ENUM(...) -- CREATE TYPE for the synthesized type is missing
│   ├── mysql_on_update_current_timestamp.py  # ON UPDATE CURRENT_TIMESTAMP -- copied into DEFAULT verbatim
│   ├── mysql_on_duplicate_key_update.py      # ON DUPLICATE KEY UPDATE -- no PostgreSQL equivalent, copied verbatim
│   ├── mysql_signal.py            # SIGNAL/RESIGNAL -- no such statement in PL/pgSQL
│   ├── mysql_fulltext_index.py    # FULLTEXT KEY/INDEX -- dropped, keywords misparsed as a column
│   ├── mysql_key_index.py         # KEY <name> (<cols>) -- mysqldump's own spelling, breaks CREATE TABLE
│   ├── mysql_spatial_index.py     # SPATIAL KEY/INDEX -- dropped, keywords misparsed as a column
│   ├── mysql_limit_comma.py       # LIMIT n, m -- PostgreSQL rejects the comma form outright
│   ├── mysql_replace_into.py      # REPLACE INTO -- copied verbatim, no PostgreSQL equivalent
│   ├── mysql_insert_ignore.py     # INSERT IGNORE -- copied verbatim, no such INSERT syntax
│   ├── mysql_prepare_from.py      # PREPARE ... FROM -- PostgreSQL spells its PREPARE differently
│   ├── mysql_last_insert_id.py    # LAST_INSERT_ID() -- no such function in PostgreSQL
│   ├── mysql_auto_increment_start.py  # AUTO_INCREMENT=<n> -- sequence start lost, PK collides
│   ├── mysql_date_format.py       # DATE_FORMAT(...) -- becomes a row constructor, silently wrong
│   ├── mysql_foreign_key.py       # FOREIGN KEY -- dropped entirely, integrity silently gone
│   ├── mysql_zero_date.py         # '0000-00-00' -- silently rewritten to a real 1970-01-01
│   ├── mysql_declare_handler.py   # DECLARE ... HANDLER -- dropped, error handling disappears
│   ├── mysql_collate.py           # COLLATE/CHARACTER SET -- dropped, comparisons change meaning
│   ├── mysql_set_type.py          # SET(...) -- becomes plain text, validation lost
│   │                             # -- MSSQL / T-SQL dialect (ora2pg -M; see mssql_lex.py) --
│   ├── mssql_bracket_identifier.py    # [dbo].[Orders] -- brackets kept in the name, breaks everything
│   ├── mssql_newid_default.py         # NEWID() -- uuid_generate_v4() without CREATE EXTENSION
│   ├── mssql_update_set.py            # UPDATE ... SET -- SET destroyed, '=' becomes ':='
│   ├── mssql_identity_column.py       # IDENTITY(1,1) -- dropped entirely, no serial, no sequence
│   ├── mssql_parameterless_procedure.py  # a no-parameter procedure gets an unparseable empty DECLARE
│   ├── mssql_if_statement.py          # IF -- no END IF with a block, no THEN without one
│   ├── mssql_raiserror.py             # RAISERROR/THROW -- copied verbatim
│   ├── mssql_try_catch.py             # BEGIN TRY/CATCH -- copied verbatim
│   ├── mssql_top_clause.py            # SELECT TOP n -- copied verbatim, no TOP in PostgreSQL
│   ├── mssql_scope_identity.py        # SCOPE_IDENTITY()/@@IDENTITY -- copied verbatim
│   ├── mssql_output_clause.py         # OUTPUT INSERTED.* -- copied verbatim, RETURNING is the equivalent
│   ├── mssql_iif.py                   # IIF() -- copied verbatim
│   ├── mssql_datediff.py              # DATEDIFF() -- copied verbatim (DATEADD/DATEPART convert fine)
│   ├── mssql_charindex.py             # CHARINDEX() -- translated, but with doubled quotes
│   ├── mssql_filtered_index.py        # CREATE INDEX ... WHERE -- dropped, though PostgreSQL has it
│   ├── mssql_foreign_key.py           # FOREIGN KEY -- dropped entirely, integrity silently gone
│   ├── mssql_collation.py             # COLLATE -- dropped, everything becomes case-insensitive citext
│   ├── mssql_computed_column.py       # a computed column is typed citext whatever it computes
│   └── mssql_rowversion.py            # ROWVERSION -> bytea, stops self-updating, locking breaks
├── mssql_lex.py                 # T-SQL-dialect lexical helpers (bracket identifiers, nested
│                               #  block comments -- the mssql_* detectors' shared base)
├── mysql_lex.py                 # MySQL/MariaDB-dialect lexical helpers (mask_strings_and_comments,
│                               #  enclosing_object_name_index -- the mysql_* detectors' shared base)
│                               #  Both re-export lex_common's dialect-independent half.
├── ora2pg_wrapper.py            # runs ora2pg per object type, parses --estimate_cost
├── i18n.py                     # output language (--lang/--set-lang): resolution, English
│                               # UI strings, and translations of detector explanations
├── verification.py             # --verify: detector-level (not line-level) status
│                               # STILL_PRESENT/NOT_DETECTED/NOT_VERIFIABLE
├── core.py                      # scan_source/count_objects/expand_paths/connect_by_check --
│                               #  the shared logic between cli.py and tui_app.py
├── cli.py                      # the ora2pg-gap-report console command
├── effort_estimator.py          # a rough severity-based heuristic, hour range
├── report_generator.py          # JSON + Markdown (machine-readable formats)
├── terminal_report.py           # colored output via rich (the only dependency;
│                               #  doesn't touch the detector library, only the CLI)
└── tui_app.py                   # --tui: an interactive screen on textual (an optional
                                 #  [tui] extra, not part of the base install)
tests/
├── fixtures/                   # real captured ora2pg runs -- the parser tests don't need
│                               # ora2pg installed, except a few live tests
│                               # (auto-skipped when ora2pg isn't found on PATH)
docs/research/                  # empirical verification of assumptions, real PL/SQL examples
docs/examples/                  # examples of detector output on real data
scripts/
├── build_offline_bundle.py     # builds a self-contained archive for offline install
├── oracle-test-compose.yml     # Oracle Free 23ai in Docker, for live verification
├── setup_oracle_test_schema.sql
└── verify_against_live_oracle.py
.github/workflows/tests.yml     # CI: pytest on 3.10-3.13 + package build and smoke test
```

## Constructs hidden inside dynamic SQL

The tool is a static analyzer: it looks for syntactic patterns in text, it
doesn't analyze execution semantics. One real, concrete instance of that
limitation: a construct built as a string inside `EXECUTE IMMEDIATE` is
completely invisible to the ordinary, blanket string/comment masking
(masking deliberately blinds the contents of every string literal, so
keywords inside a comment or a plain string don't get matched).

14 detectors that use the shared "which object surrounds this position"
index (`bulk_collect`, `connect_by_nocycle`, `cross_apply`,
`database_link`, `flashback_query`, `insert_all`, `json_table`,
`merge_delete_clause`, `model_clause`, `oracle_text`, `pivot_clause`,
`recursive_with`, `sql_macro`, `with_function`), plus `autonomous_tx`
separately (its own procedure-boundary tracking mechanism, not the shared
one), now use a second, distinct masking flavor
(`mask_dynamic_sql_visible()` in `plsql_lex.py`) in which the `EXECUTE
IMMEDIATE` argument specifically, a single literal or a `'...' ||
expression || '...'` concatenation, up to the first "bare" `;`, stays
visible instead of being blanked out. Confirmed against real open-source
code: `utPLSQL` turned up both a hidden `PRAGMA AUTONOMOUS_TRANSACTION`
(inside a dynamically created package) and a hidden `BULK COLLECT INTO`
(inside a dynamically executed anonymous block), both are now found, and
both are correctly attributed to the real procedure findable in the
source tree (not to a fictional object that only exists at execution
time), regression tests on these same real fragments live in
`tests/test_autonomous_tx.py`/`tests/test_bulk_collect.py`.

Importantly, the "which object surrounds this position" index is always
built from the safe, fully masked text, never from text with visible
dynamic SQL, otherwise a package/procedure the code creates dynamically
at runtime would get mistaken for a real object declared in the source
tree, and corrupt the attribution of unrelated findings with a name that
doesn't exist statically. This design detail is locked in by the test
`test_dynamic_sql_that_creates_a_package_at_runtime_is_not_picked_up_as_a_real_container`
in `tests/test_plsql_lex.py`.

Not covered the same way: schema-level detectors (`table_partitioning`,
`external_table`, `invisible_column`, etc., including the part of
`oracle_text` that handles `CREATE INDEX ... INDEXTYPE`) still don't see
the same-named DDL construct if it's built dynamically, a rare case in
practice (DDL is almost always static), but not verified empirically with
the same rigor, so it honestly stays outside the scope of this fix rather
than being silently assumed solved along the way.

Even where dynamic SQL visibility exists, it has its own limits.
`mask_dynamic_sql_visible()` only sees the `EXECUTE IMMEDIATE` argument
itself, a single string literal or a `'...' || expression || '...'`
concatenation directly in the call. If the query text gets assembled into
a variable piece by piece across several separate statements before the
`EXECUTE IMMEDIATE` itself (`l_sql := 'BULK'; l_sql := l_sql || '
COLLECT INTO ...'; ... EXECUTE IMMEDIATE l_sql;`), only the final
variable is visible, how exactly it was assembled isn't tracked.
Separately: dynamic SQL via the old `DBMS_SQL.PARSE`/`DBMS_SQL.EXECUTE`
API (not `EXECUTE IMMEDIATE`) isn't supported at all, no detector looks
for it. Both cases are rarer in practice than a direct `EXECUTE IMMEDIATE`
with a literal or concatenation (which was enough to produce real
findings in `utPLSQL`, see above), but haven't been verified empirically
with the same rigor.

## Memory on a large scan

Every report format is written straight to its destination -- a file
opened atomically, or stdout -- rather than built as a string first.
`report_generator.py` exposes both shapes for each format: `to_json()`
and friends return a string (what tests and `--verify` use), `write_json()`
and friends write to a stream (what a scan uses). They are the same code;
`tests/test_streaming_report.py` compares them byte for byte in both
languages, for every format, empty and non-empty.

This is worth the second entry point because the report, not the scan, was
the memory ceiling. Measured on an 1,800-file corpus producing 77,800
findings:

| | before | after |
|---|---|---|
| holding all findings | 39 MB | 39 MB |
| `--format json` | 246 MB | 54 MB |
| `--format csv` | 489 MB | 54 MB |
| `--format markdown` | 515 MB | 54 MB |
| `--format html` | 582 MB | 54 MB |
| `--format sarif` | 682 MB | 54 MB |

Two things were paying for that. `json.dumps` is literally
`"".join(iterencode(o))`, and for a large document that join is the
biggest allocation in the process -- a few million short chunk strings and
the list holding them. And each format built a full intermediate
structure, one dict per finding, before encoding began. Writing the
surrounding document once and each item as it is produced removes both;
`_stream_json_with_array()` handles the JSON-shaped formats by encoding
the document with a placeholder where the big array goes, then cutting it
open there, so indentation and escaping still come from the stdlib
encoder rather than from braces written by hand.

What remains is the findings list itself, at roughly 22 KB per 1,000
findings. That is a real floor, not an oversight: `--save`, `--fail-on`,
`--baseline` and the sort that orders the report all need the complete
set before any of them can answer. A scan large enough for that to matter
would need the findings spilled to disk, which is a different design than
this one, and not one any real schema has called for yet.

## Post-migration verification (`--verify`)

`--verify` compares pre-migration findings (a `--save` snapshot) against
what's statically visible in the already-generated ora2pg PostgreSQL
code, at detector granularity, not per finding (file/object/snippet
matching, like `baseline.py` uses, doesn't survive the Oracle→PostgreSQL
boundary: ora2pg renames objects, e.g. `autonomous_tx`'s own dblink
strategy appends an `_atx` suffix, and the file is different either way).
Implemented in `verification.py`.

This is not a behavioral/functional check: the tool never connects to
either database, never executes anything, never compares data. It simply
runs the same detectors against the generated file instead of the
original Oracle file, and that doesn't work the same way for all 38
detectors, because not every construct survives conversion the same way:

- **`VERBATIM`** (21 detectors) — `ora2pg` copies the flagged Oracle
  construct into its output essentially unchanged (confirmed from each
  detector's own research doc, the "what ora2pg does" section):
  `bulk_collect`, `conditional_compilation`, `cross_apply`,
  `database_link`, `dbms_utl_calls`, `default_on_null`,
  `flashback_query`, `identity_column`, `insert_all`, `json_table`,
  `merge_delete_clause`, `model_clause`, `object_type`, `pivot_clause`,
  `recursive_with`. For these, re-running the same detector against the
  generated file is a real check: `STILL_PRESENT` if the pattern remains,
  `NOT_DETECTED` if it's gone.

- **`NOT_VERIFIABLE`** (26 detectors) — `ora2pg` either drops the
  construct entirely or rewrites it into a completely different shape
  (`read_only_table`, `table_partitioning`, `invisible_column`,
  `invisible_index`, `external_table`, `collection_type`,
  `context_object`, `materialized_view_log`, `sql_macro`, `rowid_type`,
  `sequence_cycle`, `index_organized_table`, `public_synonym`: rewritten
  into a `CREATE VIEW`, the `SYNONYM`/`FOR` keywords don't survive
  conversion; `virtual_column`: rewritten into a plain column + trigger,
  `GENERATED ALWAYS AS ... VIRTUAL` doesn't survive conversion;
  `package_state`: a package variable rewritten into
  `set_config`/`current_setting` calls, the declaration itself doesn't
  survive conversion — the specific keyword/type the detector looks for
  physically cannot end up in the output for any migration, regardless of
  whether someone worked around the problem by hand some other way), or
  it flattens the surrounding structure so badly (`with_function`,
  `connect_by_nocycle`, `nested_subprogram`: nesting is completely
  flattened on export, re-detecting the structure itself can't be
  trusted, see each one's own research doc, "flattens the structure")
  that a clean re-detection can't be trusted. `oracle_text` is mixed (the
  domain index itself is dropped, `CONTAINS`/`CATSEARCH`/`MATCHES` calls
  are copied as-is) and is conservatively classified entirely as
  `NOT_VERIFIABLE`. `autonomous_tx` is `NOT_VERIFIABLE` for a different
  reason: its finding isn't about the shape of the code at all, it's
  about `SHOW_REPORT`/`--estimate_cost` underestimating cost, there's
  nothing to re-check after the fact. Showing `NOT_DETECTED` for any of
  these would be a tautology (the construct is guaranteed to be absent
  from the output on *any* migration), so `--verify` says
  `NOT_VERIFIABLE` explicitly instead.

- **`connect_by`** falls into neither category: it already only analyzes
  generated code (`--check-connect-by`), so it has no separate
  pre-migration Oracle finding for `--verify` to compare against.

`scripts/doctor.py` checks that every real detector on disk has an entry
in `VERIFICATION_MODE`, the same class of check as for
`EXPLANATION_EN`/`REMEDIATION_HINT_EN`.

A per-gap table of this mode (not just by category, as above) is in
[`docs/verification-capability-matrix.md`](verification-capability-matrix.md).
