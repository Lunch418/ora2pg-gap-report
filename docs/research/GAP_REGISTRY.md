# Registry of confirmed gaps

Every row is a specific construct of a source dialect (Oracle;
MySQL/MariaDB through `ora2pg -m` from GAP-068 on; or T-SQL/SQL Server
through `ora2pg -M` from GAP-087 on — see the `GapEntry.dialect` field in
`gap_registry.py`) for which it has been empirically confirmed — not
assumed — that `ora2pg` converts it incorrectly or skips it without
warning. See "Methodology" in the main [README](../../README.md): a
detector appears only after a hypothesis has been through that cycle.
Rejected hypotheses do not enter the registry — they are documented
separately, in `step0-show-report-baseline.md` (section 1 and part of 4)
and `rejected-hypotheses.md`.

The numbers were assigned in the order things were documented, not by
importance or by the order of implementation — GAP-002/003 were
documented before GAP-001/004/005 simply because the registry came into
being after them.

| ID | Construct | Detector | Severity | Status | ora2pg | PostgreSQL | Verified | Document |
|---|---|---|---|---|---|---|---|---|
| GAP-001 | `PRAGMA AUTONOMOUS_TRANSACTION` — cost underestimated in a package body | `autonomous_tx` | high | confirmed | 25.0 | 16 | 2026-08-14 | [gap-001](gap-001-autonomous-transaction.md) |
| GAP-002 | `MERGE ... WHEN MATCHED THEN UPDATE SET ... DELETE WHERE ...` | `merge_delete_clause` | high | confirmed | 25.0 | 16 | 2026-08-14 | [gap-002](gap-002-merge-delete-clause.md) |
| GAP-003 | `TYPE ... IS TABLE OF` / `BULK COLLECT INTO` / `FORALL` | `bulk_collect` | high | confirmed | 25.0 | 16 | 2026-08-14 | [gap-003](gap-003-bulk-collect-forall.md) |
| GAP-004 | `COMPOUND TRIGGER` — silent failure of the file parser | `compound_triggers` | high | confirmed | 25.0 | 16 | 2026-08-14 | [gap-004](gap-004-compound-trigger.md) |
| GAP-005 | `CONNECT BY` — `LEVEL` substitution bug in `WITH RECURSIVE` | `connect_by` | high | confirmed | 25.0 | 16 | 2026-08-14 | [gap-005](gap-005-connect-by-level.md) |
| GAP-006 | `table@dblink_name` — a direct reference to a remote database | `database_link` | high | confirmed | 25.0 | 16 | 2026-08-14 | [gap-006](gap-006-database-link.md) |
| GAP-007 | `MODEL PARTITION BY ... DIMENSION BY ... MEASURES ... RULES` | `model_clause` | high | confirmed | 25.0 | 16 | 2026-08-14 | [gap-007](gap-007-model-clause.md) |
| GAP-008 | `PIVOT`/`UNPIVOT` | `pivot_clause` | high | confirmed | 25.0 | 16 | 2026-08-14 | [gap-008](gap-008-pivot-unpivot.md) |
| GAP-009 | `CREATE TYPE ... AS OBJECT` / `TYPE BODY` — outside the effort estimate entirely | `object_type` | high | confirmed | 25.0 | 16 | 2026-08-14 | [gap-009](gap-009-object-type.md) |
| GAP-010 | `WITH FUNCTION`/`WITH PROCEDURE` — the parser wrecks the source structure | `with_function` | high | confirmed | 25.0 | 16 | 2026-08-14 | [gap-010](gap-010-with-function.md) |
| GAP-011 | `AS OF TIMESTAMP`/`AS OF SCN` — a flashback query | `flashback_query` | high | confirmed | 25.0 | 16 | 2026-08-14 | [gap-011](gap-011-flashback-query.md) |
| GAP-012 | `CREATE GLOBAL TEMPORARY TABLE` — the `ON COMMIT` clause is lost | `global_temp_table` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-012](gap-012-global-temp-table.md) |
| GAP-013 | `PARTITION BY RANGE/LIST/HASH` — table partitioning is dropped entirely | `table_partitioning` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-013](gap-013-table-partitioning.md) |
| GAP-014 | `CONNECT BY NOCYCLE` / `ORDER SIBLINGS BY` — structural destruction of the block | `connect_by_nocycle` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-014](gap-014-connect-by-nocycle.md) |
| GAP-015 | `CREATE CONTEXT` — an application context is not converted at all | `context_object` | medium | confirmed | 25.0 | 16 | 2026-08-15 | [gap-015](gap-015-context.md) |
| GAP-016 | `INSERT ALL`/`INSERT FIRST` — a multi-table insert | `insert_all` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-016](gap-016-insert-all.md) |
| GAP-017 | `JSON_TABLE(...)` — does not exist in PostgreSQL 16 or earlier | `json_table` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-017](gap-017-json-table.md) |
| GAP-018 | `CREATE TABLE ... ORGANIZATION EXTERNAL` — the clause is dropped entirely | `external_table` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-018](gap-018-external-table.md) |
| GAP-019 | `SQL_MACRO` — converted into an ordinary function | `sql_macro` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-019](gap-019-sql-macro.md) |
| GAP-020 | An `INVISIBLE` column loses its invisibility | `invisible_column` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-020](gap-020-invisible-column.md) |
| GAP-021 | `CREATE TYPE ... TABLE OF`/`VARRAY OF` — a collection type vanishes without a trace | `collection_type` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-021](gap-021-collection-type.md) |
| GAP-022 | `CROSS APPLY`/`OUTER APPLY` — PostgreSQL has no APPLY syntax | `cross_apply` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-022](gap-022-cross-apply.md) |
| GAP-023 | Oracle Text — the domain index is dropped, `CONTAINS`/`CATSEARCH`/`MATCHES` do not port | `oracle_text` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-023](gap-023-oracle-text.md) |
| GAP-024 | A natively recursive `WITH ... AS (...)` without the `RECURSIVE` keyword | `recursive_with` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-024](gap-024-recursive-with.md) |
| GAP-025 | An `INVISIBLE` index loses its invisibility to the optimizer | `invisible_index` | medium | confirmed | 25.0 | 16 | 2026-08-15 | [gap-025](gap-025-invisible-index.md) |
| GAP-026 | `CREATE TABLE ... READ ONLY` loses its immutability guarantee | `read_only_table` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-026](gap-026-read-only-table.md) |
| GAP-027 | `CREATE MATERIALIZED VIEW LOG` is not converted at all | `materialized_view_log` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-027](gap-027-materialized-view-log.md) |
| GAP-028 | `GENERATED ... AS IDENTITY (...)` with options — a doubled-parenthesis bug | `identity_column` | high | confirmed | 25.0 | 16 | 2026-08-15 | [gap-028](gap-028-identity-column.md) |
| GAP-029 | `ROWID`/`UROWID` as a column type — converted to an incompatible `oid` | `rowid_type` | high | confirmed | 25.0 | 16 | 2026-08-17 | [gap-029](gap-029-rowid-urowid.md) |
| GAP-030 | `CREATE SEQUENCE ... CYCLE` — the `CYCLE` clause is dropped | `sequence_cycle` | high | confirmed | 25.0 | 16 | 2026-08-17 | [gap-030](gap-030-sequence-cycle.md) |
| GAP-031 | `DEFAULT ON NULL` copied verbatim — a syntax error | `default_on_null` | high | confirmed | 25.0 | 16 | 2026-08-17 | [gap-031](gap-031-default-on-null.md) |
| GAP-032 | `CREATE [PUBLIC] SYNONYM` — loses the target object's schema | `public_synonym` | high | confirmed | 25.0 | 16 | 2026-08-17 | [gap-032](gap-032-public-synonym.md) |
| GAP-033 | `GENERATED ALWAYS AS (...) VIRTUAL` — loses the `ORA-54016` protection | `virtual_column` | medium | confirmed | 25.0 | 16 | 2026-08-17 | [gap-033](gap-033-virtual-column.md) |
| GAP-034 | A local nested procedure/function — corrupted on export | `nested_subprogram` | high | confirmed | 25.0 | 16 | 2026-08-17 | [gap-034](gap-034-nested-subprogram.md) |
| GAP-035 | `$IF`/`$ELSIF`/`$ELSE`/`$END` copied verbatim | `conditional_compilation` | high | confirmed | 25.0 | 16 | 2026-08-17 | [gap-035](gap-035-conditional-compilation.md) |
| GAP-036 | A package variable — a broken emulation through `set_config` | `package_state` | high | confirmed | 25.0 | 16 | 2026-08-17 | [gap-036](gap-036-package-state.md) |
| GAP-037 | `ORGANIZATION INDEX` (IOT) is dropped | `index_organized_table` | medium | confirmed | 25.0 | 16 | 2026-08-17 | [gap-037](gap-037-index-organized-table.md) |
| GAP-038 | `MATCH_RECOGNIZE` — row pattern matching, no PostgreSQL counterpart | `match_recognize` | high | confirmed | 25.0 | 16 | 2026-08-27 | [gap-038](gap-038-match-recognize.md) |
| GAP-039 | `CONNECT_BY_ROOT`/`CONNECT_BY_ISLEAF`/`CONNECT_BY_ISCYCLE` are carried over unconverted | `connect_by_pseudocolumn` | high | confirmed | 25.0 | 16 | 2026-08-27 | [gap-039](gap-039-connect-by-pseudocolumn.md) |
| GAP-040 | `KEEP (DENSE_RANK FIRST/LAST ORDER BY ...)` — an aggregate modifier | `keep_dense_rank` | high | confirmed | 25.0 | 16 | 2026-08-27 | [gap-040](gap-040-keep-dense-rank.md) |
| GAP-041 | `CAST(MULTISET(...))`, `MULTISET UNION`, `MEMBER OF`, `SUBMULTISET OF` | `multiset_operator` | high | confirmed | 25.0 | 16 | 2026-08-27 | [gap-041](gap-041-multiset-operator.md) |
| GAP-042 | `SAMPLE (n)` — this is `TABLESAMPLE` in PostgreSQL, ora2pg does not convert it | `sample_clause` | high | confirmed | 25.0 | 16 | 2026-08-27 | [gap-042](gap-042-sample-clause.md) |
| GAP-043 | `ACCESSIBLE BY` is copied into the generated function's header | `accessible_by` | high | confirmed | 25.0 | 16 | 2026-08-27 | [gap-043](gap-043-accessible-by.md) |
| GAP-044 | `TIMESTAMP WITH LOCAL TIME ZONE` → `timestamp` without a time zone | `local_time_zone` | high | confirmed | 25.0 | 16 | 2026-08-27 | [gap-044](gap-044-local-time-zone.md) |
| GAP-045 | `PERIOD FOR` (Temporal Validity) becomes the stub `period FOR` | `temporal_validity` | high | confirmed | 25.0 | 16 | 2026-08-27 | [gap-045](gap-045-temporal-validity.md) |
| GAP-046 | `CREATE BITMAP INDEX` → `USING gin` without an operator class | `bitmap_index` | high | confirmed | 25.0 | 16 | 2026-08-27 | [gap-046](gap-046-bitmap-index.md) |
| GAP-047 | `CREATE TABLE ... OF <type>` — `OF` becomes a column name | `object_table` | high | confirmed | 25.0 | 16 | 2026-08-27 | [gap-047](gap-047-object-table.md) |
| GAP-048 | `IGNORE NULLS` / `RESPECT NULLS` — no such syntax in PostgreSQL 16 | `ignore_nulls` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-048](gap-048-ignore-nulls.md) |
| GAP-049 | `NLSSORT` — becomes a `COLLATE` with a non-existent collation name | `nlssort` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-049](gap-049-nlssort.md) |
| GAP-050 | `LONG RAW` maps to `text` rather than the documented `bytea` | `long_raw_type` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-050](gap-050-long-raw-type.md) |
| GAP-051 | `SYS.ANYDATA` — the type name is copied, PostgreSQL has no `SYS` schema | `anydata_type` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-051](gap-051-anydata-type.md) |
| GAP-052 | System triggers (`ON DATABASE`/`ON SCHEMA`) are emitted as table triggers | `system_trigger` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-052](gap-052-system-trigger.md) |
| GAP-053 | `FOLLOWS`/`PRECEDES` ends up inside the trigger function body | `trigger_follows` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-053](gap-053-trigger-follows.md) |
| GAP-054 | The `TABLE(...)` operator — collection unnesting, copied as-is | `table_collection` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-054](gap-054-table-collection.md) |
| GAP-055 | `CURSOR(SELECT ...)` — a cursor expression, no counterpart | `cursor_expression` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-055](gap-055-cursor-expression.md) |
| GAP-056 | `FOR UPDATE ... WAIT n` — only `NOWAIT`/`SKIP LOCKED` exist | `for_update_wait` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-056](gap-056-for-update-wait.md) |
| GAP-057 | `ROWNUM` in `UPDATE`/`DELETE` becomes an invalid `LIMIT` | `rownum_dml` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-057](gap-057-rownum-dml.md) |
| GAP-058 | The `RR` format in `TO_DATE` — silently returns the year 1 BC | `to_date_rr` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-058](gap-058-to-date-rr.md) |
| GAP-059 | `AUTHID` — the procedure silently disappears from the output entirely | `authid_clause` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-059](gap-059-authid-clause.md) |
| GAP-060 | `PRAGMA EXCEPTION_INIT` — the handler gets someone else's `SQLSTATE '50001'` | `pragma_exception_init` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-060](gap-060-pragma-exception-init.md) |
| GAP-061 | `SUBTYPE ... RANGE` is carried into `CREATE DOMAIN` verbatim | `subtype_range` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-061](gap-061-subtype-range.md) |
| GAP-062 | `q'[...]'` — alternative quoting, copied as-is | `alt_quote_literal` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-062](gap-062-alt-quote-literal.md) |
| GAP-063 | `GOTO` — PL/pgSQL has no such statement | `goto_statement` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-063](gap-063-goto-statement.md) |
| GAP-064 | `<cursor>%ROWTYPE` — PL/pgSQL allows only a table/view | `cursor_rowtype` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-064](gap-064-cursor-rowtype.md) |
| GAP-065 | `WM_CONCAT` is copied as-is, unlike `LISTAGG` | `wm_concat` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-065](gap-065-wm-concat.md) |
| GAP-066 | `WITH READ ONLY` is dropped — the view becomes updatable | `read_only_view` | high | confirmed | 25.0 | 16 | 2026-08-28 | [gap-066](gap-066-read-only-view.md) |
| GAP-067 | `SDO_GEOMETRY` — a PostGIS type without `CREATE EXTENSION postgis` | `sdo_geometry` | medium | confirmed | 25.0 | 16 | 2026-08-28 | [gap-067](gap-067-sdo-geometry.md) |

### MySQL/MariaDB (`ora2pg -m`, `dialect="mysql"`)

| ID | Construct | Detector | Severity | Status | ora2pg | PostgreSQL | Verified | Document |
|---|---|---|---|---|---|---|---|---|
| GAP-068 | `ENUM(...)` — a reference to a synthesized type that is never created | `mysql_enum_type` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-068](gap-068-mysql-enum-type.md) |
| GAP-069 | `DEFAULT ... ON UPDATE CURRENT_TIMESTAMP` — invalid syntax inside DEFAULT | `mysql_on_update_current_timestamp` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-069](gap-069-mysql-on-update-current-timestamp.md) |
| GAP-070 | `INSERT ... ON DUPLICATE KEY UPDATE` — copied as-is, no counterpart | `mysql_on_duplicate_key_update` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-070](gap-070-mysql-on-duplicate-key-update.md) |
| GAP-071 | `SIGNAL`/`RESIGNAL` — copied as-is, PL/pgSQL has no such statement | `mysql_signal` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-071](gap-071-mysql-signal.md) |
| GAP-072 | `FULLTEXT KEY`/`FULLTEXT INDEX` — lost entirely, breaks CREATE TABLE | `mysql_fulltext_index` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-072](gap-072-mysql-fulltext-index.md) |
| GAP-073 | `KEY <name> (<columns>)` — the mysqldump spelling, breaks CREATE TABLE | `mysql_key_index` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-073](gap-073-mysql-key-index.md) |
| GAP-074 | `SPATIAL KEY`/`SPATIAL INDEX` — lost entirely, breaks CREATE TABLE | `mysql_spatial_index` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-074](gap-074-mysql-spatial-index.md) |
| GAP-075 | `LIMIT <offset>, <count>` — PostgreSQL does not accept this form | `mysql_limit_comma` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-075](gap-075-mysql-limit-comma.md) |
| GAP-076 | `REPLACE INTO` — copied as-is, no counterpart | `mysql_replace_into` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-076](gap-076-mysql-replace-into.md) |
| GAP-077 | `INSERT IGNORE` — copied as-is, no such syntax | `mysql_insert_ignore` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-077](gap-077-mysql-insert-ignore.md) |
| GAP-078 | `PREPARE <name> FROM` — PostgreSQL's PREPARE has different syntax | `mysql_prepare_from` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-078](gap-078-mysql-prepare-from.md) |
| GAP-079 | `LAST_INSERT_ID()` — no such function in PostgreSQL | `mysql_last_insert_id` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-079](gap-079-mysql-last-insert-id.md) |
| GAP-080 | `AUTO_INCREMENT=<n>` — start value lost on the file-based path (live-DB export gets it right) | `mysql_auto_increment_start` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-080](gap-080-mysql-auto-increment-start.md) |
| GAP-081 | `DATE_FORMAT(...)` — silently returns a tuple instead of a string | `mysql_date_format` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-081](gap-081-mysql-date-format.md) |
| GAP-082 | `FOREIGN KEY` dropped when PG_VERSION is left at its unset default (<=12) | `mysql_foreign_key` | high | confirmed | 25.0 | 16 | 2026-09-08 | [gap-082](gap-082-mysql-foreign-key.md) |
| GAP-083 | `'0000-00-00'` silently becomes the real date `'1970-01-01'` | `mysql_zero_date` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-083](gap-083-mysql-zero-date.md) |
| GAP-084 | `DECLARE ... HANDLER` is dropped — error handling disappears | `mysql_declare_handler` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-084](gap-084-mysql-declare-handler.md) |
| GAP-085 | `COLLATE`/`CHARACTER SET` is dropped — string comparison changes meaning | `mysql_collate` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-085](gap-085-mysql-collate.md) |
| GAP-086 | `SET(...)` becomes `text` — validation of allowed values is lost | `mysql_set_type` | medium | confirmed | 25.0 | 16 | 2026-09-01 | [gap-086](gap-086-mysql-set-type.md) |

### MSSQL / T-SQL (`ora2pg -M`, `dialect="mssql"`)

| ID | Construct | Detector | Severity | Status | ora2pg | PostgreSQL | Verified | Document |
|---|---|---|---|---|---|---|---|---|
| GAP-087 | Bracketed identifiers are not unwrapped — breaks any SSMS script | `mssql_bracket_identifier` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-087](gap-087-mssql-bracket-identifier.md) |
| GAP-088 | `NEWID()` → `uuid_generate_v4()` without `CREATE EXTENSION "uuid-ossp"` | `mssql_newid_default` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-088](gap-088-mssql-newid-default.md) |
| GAP-089 | `UPDATE ... SET` turns into a `:=` assignment | `mssql_update_set` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-089](gap-089-mssql-update-set.md) |
| GAP-090 | `IDENTITY(1,1)` disappears on the file-based path — inserts fail on NOT NULL | `mssql_identity_column` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-090](gap-090-mssql-identity-column.md) |
| GAP-091 | A parameterless procedure gets an unparseable empty `DECLARE` | `mssql_parameterless_procedure` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-091](gap-091-mssql-parameterless-procedure.md) |
| GAP-092 | `IF` is not completed into `THEN ... END IF` | `mssql_if_statement` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-092](gap-092-mssql-if-statement.md) |
| GAP-093 | `RAISERROR`/`THROW` are copied as-is | `mssql_raiserror` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-093](gap-093-mssql-raiserror.md) |
| GAP-094 | `BEGIN TRY`/`BEGIN CATCH` are copied as-is | `mssql_try_catch` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-094](gap-094-mssql-try-catch.md) |
| GAP-095 | `SELECT TOP n` is copied as-is | `mssql_top_clause` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-095](gap-095-mssql-top-clause.md) |
| GAP-096 | `SCOPE_IDENTITY()`/`@@IDENTITY` are copied as-is | `mssql_scope_identity` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-096](gap-096-mssql-scope-identity.md) |
| GAP-097 | `OUTPUT INSERTED.*` is copied as-is | `mssql_output_clause` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-097](gap-097-mssql-output-clause.md) |
| GAP-098 | `IIF()` is copied as-is | `mssql_iif` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-098](gap-098-mssql-iif.md) |
| GAP-099 | `DATEDIFF()` is copied as-is (`DATEADD`/`DATEPART` are not) | `mssql_datediff` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-099](gap-099-mssql-datediff.md) |
| GAP-100 | `CHARINDEX()` → `position()` with doubled quotes | `mssql_charindex` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-100](gap-100-mssql-charindex.md) |
| GAP-101 | A filtered index (`CREATE INDEX ... WHERE`) is dropped | `mssql_filtered_index` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-101](gap-101-mssql-filtered-index.md) |
| GAP-102 | `FOREIGN KEY` dropped when PG_VERSION is left at its unset default (<=12) | `mssql_foreign_key` | high | confirmed | 25.0 | 16 | 2026-09-08 | [gap-102](gap-102-mssql-foreign-key.md) |
| GAP-103 | `COLLATE` ignored, everything becomes case-insensitive `citext` by default | `mssql_collation` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-103](gap-103-mssql-collation.md) |
| GAP-104 | A computed column gets the type `citext` regardless of the expression | `mssql_computed_column` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-104](gap-104-mssql-computed-column.md) |
| GAP-105 | `ROWVERSION` → `bytea`, stops updating — optimistic locking breaks | `mssql_rowversion` | high | confirmed | 25.0 | 16 | 2026-09-01 | [gap-105](gap-105-mssql-rowversion.md) |

Statuses: `confirmed` — reproduced on the stated ora2pg version and still
current; `fixed-upstream` — ora2pg fixed the problem in a newer version
(the detector still exists in that case, but must be explicitly marked
obsolete); `wont-fix` — the problem is architectural and unlikely to be
fixed upstream. None of these statuses is checked automatically — each is
a manual note made when the research was done, not live monitoring of
ora2pg releases. If you find that a newer ora2pg has fixed one of these
gaps, please open an issue.

`dbms_utl_calls` is a separate case and does not enter the registry as a
single GAP: it is not one specific construct but a general classifier for
specific `DBMS_*`/`UTL_*` calls (the list of the ones that do convert is
in the detector itself, `_CONVERTED` in `dbms_utl_calls.py`). The overall
conclusion for the whole class is documented in
`step0-show-report-baseline.md`, section 4.
