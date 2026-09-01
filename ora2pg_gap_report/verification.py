"""Post-migration static verification: after `ora2pg` has produced its
PostgreSQL output, checks which pre-migration findings (`--save`d as a
baseline) are still statically visible in that output.

This is deliberately NOT behavioral/functional verification -- it never
connects to a database, runs a query, or claims the migration "works".
It answers a narrower, honestly answerable question: for each detector
that fired before migration, does the exact same static pattern still
appear in the generated code? See the module-level classification below
for why that question isn't even meaningful for every detector.

## Why detectors split into two groups

A detector's pre-migration finding is a pattern in *Oracle* source. What
happens to that exact pattern in ora2pg's *generated PostgreSQL* varies
by detector, and that variation is the entire reason this module exists
rather than just re-running every detector against the output file
unconditionally:

- **VERBATIM** detectors: ora2pg copies the flagged Oracle construct into
  its output essentially unchanged (confirmed per-detector in each
  docs/research/gap-*.md doc's own "что делает ora2pg" section -- e.g.
  `CROSS APPLY(...)`, `PIVOT`, `JSON_TABLE(...)`, a raw `table@dblink`
  reference). Re-running the same detector against the generated file is
  a real, meaningful check: if the pattern is gone, someone genuinely
  rewrote that code by hand.

- **NOT_VERIFIABLE** detectors: ora2pg either drops the flagged construct
  entirely (`READ ONLY`, `PARTITION BY`, `INVISIBLE`, the whole
  `ORGANIZATION EXTERNAL` clause -- the Oracle-specific keyword the
  detector looks for is *never* going to be in the output, by
  construction, regardless of whether anyone fixed the underlying
  problem some other way) or mangles the surrounding structure badly
  enough that a clean re-detection can't be trusted (`with_function`,
  `connect_by_nocycle` -- see their own research docs for "разваливает
  структуру"). Re-running these against the output would report
  "not detected" on *every single migration*, unconditionally -- not a
  signal, a tautology. Reporting that as if it meant something would be
  exactly the kind of manufactured confidence this project's effort
  estimate and severity criteria already go out of their way to avoid.

`autonomous_tx` is NOT_VERIFIABLE for a different reason: its finding is
about SHOW_REPORT/--estimate_cost underestimating migration *cost*, not
about broken generated code -- there's no code-shape question to
re-check post-migration at all.

`connect_by` doesn't appear in either bucket: it already only ever
analyzes ora2pg's generated output (see cli.py's --check-connect-by), so
it has no separate "pre-migration Oracle-side finding" for this module
to compare against in the first place -- there is nothing for `verify`
to do with it.

scripts/doctor.py cross-checks VERIFICATION_MODE against every real
detector on disk, same drift-prevention pattern as EXPLANATION_EN.
"""

import dataclasses

from .gap_registry import gap_by_detector
from .models import Finding

VERBATIM = "verbatim"
NOT_VERIFIABLE = "not_verifiable"
GENERATED_ONLY = "generated_only"  # connect_by -- see module docstring

VERIFICATION_MODE: dict[str, str] = {
    # VERBATIM -- ora2pg copies the flagged construct into its output
    # essentially unchanged; re-running the detector against the output
    # is a real check.
    "merge_delete_clause": VERBATIM,
    "bulk_collect": VERBATIM,
    "database_link": VERBATIM,
    "model_clause": VERBATIM,
    "pivot_clause": VERBATIM,
    "object_type": VERBATIM,
    "flashback_query": VERBATIM,
    "insert_all": VERBATIM,
    "json_table": VERBATIM,
    "cross_apply": VERBATIM,
    "recursive_with": VERBATIM,
    "identity_column": VERBATIM,
    "dbms_utl_calls": VERBATIM,
    "default_on_null": VERBATIM,  # the ON NULL clause itself is copied into CREATE TABLE unchanged
    "conditional_compilation": VERBATIM,  # $IF/$ELSIF/$ELSE/$END are copied into the body unchanged
    "match_recognize": VERBATIM,  # the whole MATCH_RECOGNIZE(...) clause is copied unchanged
    "connect_by_pseudocolumn": VERBATIM,  # CONNECT_BY_ROOT/ISLEAF/ISCYCLE survive into the generated CTE
    "keep_dense_rank": VERBATIM,  # KEEP(DENSE_RANK ...) is copied unchanged
    "multiset_operator": VERBATIM,  # MULTISET/MEMBER OF/SUBMULTISET are copied unchanged
    "sample_clause": VERBATIM,  # SAMPLE(n) is copied unchanged
    "accessible_by": VERBATIM,  # the clause is copied verbatim into the generated function header
    "ignore_nulls": VERBATIM,  # IGNORE/RESPECT NULLS is copied unchanged
    "anydata_type": VERBATIM,  # the SYS.ANYDATA type name is copied unchanged
    "system_trigger": VERBATIM,  # the ON DATABASE/SCHEMA scope survives (lowercased) in the generated CREATE TRIGGER
    "table_collection": VERBATIM,  # the TABLE(...) operator is copied unchanged
    "cursor_expression": VERBATIM,  # CURSOR(SELECT ...) is copied unchanged
    "for_update_wait": VERBATIM,  # the WAIT n clause is copied unchanged
    "to_date_rr": VERBATIM,  # the RR format model is left in place inside TO_DATE
    "alt_quote_literal": VERBATIM,  # the q'...' literal is copied unchanged
    "goto_statement": VERBATIM,  # GOTO and its label are copied unchanged
    "wm_concat": VERBATIM,  # the WM_CONCAT call is copied unchanged (unlike LISTAGG)
    # NOT_VERIFIABLE -- ora2pg drops the construct entirely (the
    # Oracle-specific keyword the detector looks for cannot appear in the
    # output, by construction, on any migration) or mangles the
    # surrounding structure too unpredictably to re-detect cleanly.
    "autonomous_tx": NOT_VERIFIABLE,  # cost-estimation finding, not a code-shape one
    "compound_triggers": NOT_VERIFIABLE,
    "with_function": NOT_VERIFIABLE,
    "global_temp_table": NOT_VERIFIABLE,
    "table_partitioning": NOT_VERIFIABLE,
    "connect_by_nocycle": NOT_VERIFIABLE,
    "context_object": NOT_VERIFIABLE,
    "external_table": NOT_VERIFIABLE,
    "invisible_column": NOT_VERIFIABLE,
    "collection_type": NOT_VERIFIABLE,
    "oracle_text": NOT_VERIFIABLE,  # mixed: INDEXTYPE is dropped, CONTAINS()/... is copied as-is
    "invisible_index": NOT_VERIFIABLE,
    "read_only_table": NOT_VERIFIABLE,
    "materialized_view_log": NOT_VERIFIABLE,
    "sql_macro": NOT_VERIFIABLE,  # the SQL_MACRO keyword itself is dropped unconditionally
    "rowid_type": NOT_VERIFIABLE,  # ROWID/UROWID is rewritten to oid, the keyword never survives
    "sequence_cycle": NOT_VERIFIABLE,  # the CYCLE keyword itself is dropped unconditionally
    "public_synonym": NOT_VERIFIABLE,  # rewritten to CREATE VIEW; SYNONYM/FOR never survive
    "virtual_column": NOT_VERIFIABLE,  # rewritten to a plain column + trigger; the clause never survives
    "nested_subprogram": NOT_VERIFIABLE,  # the nesting itself is flattened away; structure not re-detectable
    "package_state": NOT_VERIFIABLE,  # rewritten to set_config/current_setting; the declaration never survives
    "index_organized_table": NOT_VERIFIABLE,  # the ORGANIZATION INDEX keyword itself is dropped unconditionally
    "local_time_zone": NOT_VERIFIABLE,  # rewritten to a bare `timestamp`; WITH LOCAL TIME ZONE never survives
    "temporal_validity": NOT_VERIFIABLE,  # mangled to a bare `period FOR`; the named PERIOD FOR shape never survives
    "bitmap_index": NOT_VERIFIABLE,  # rewritten to CREATE INDEX ... USING gin; the BITMAP keyword never survives
    "object_table": NOT_VERIFIABLE,  # OF <type> becomes a column named `of`; the object-table shape never survives
    "nlssort": NOT_VERIFIABLE,  # rewritten to a COLLATE clause; the NLSSORT call never survives
    "long_raw_type": NOT_VERIFIABLE,  # rewritten to `text`; the LONG RAW keyword never survives
    # trigger_follows: the clause *does* survive, but into the generated
    # trigger *function's* body -- not into the CREATE TRIGGER header,
    # which is the only place this detector looks (deliberately, since
    # FOLLOWS is an ordinary identifier elsewhere). So it is verbatim in
    # the file and still not re-detectable, which is exactly what
    # NOT_VERIFIABLE means here.
    "trigger_follows": NOT_VERIFIABLE,
    "rownum_dml": NOT_VERIFIABLE,  # rewritten to LIMIT n; the ROWNUM keyword never survives
    "authid_clause": NOT_VERIFIABLE,  # the whole routine is dropped, so nothing at all reaches the output
    "pragma_exception_init": NOT_VERIFIABLE,  # the pragma is dropped; only a placeholder SQLSTATE remains
    "subtype_range": NOT_VERIFIABLE,  # becomes CREATE DOMAIN; the SUBTYPE keyword never survives
    "cursor_rowtype": NOT_VERIFIABLE,  # %ROWTYPE survives but `CURSOR c IS` becomes `c CURSOR FOR`, so the cursor name no longer resolves
    "read_only_view": NOT_VERIFIABLE,  # the WITH READ ONLY clause is dropped unconditionally
    "sdo_geometry": NOT_VERIFIABLE,  # rewritten to PostGIS `geometry`; the SDO_GEOMETRY name never survives
    # MySQL dialect detectors -- note --verify itself doesn't accept
    # --dialect mysql yet (see cli.py), so none of these are actually
    # reachable through --verify today. Still classified here because
    # doctor.py's check_verification_mode_parity requires an entry for
    # every detector on disk regardless, and the classification itself
    # (what does ora2pg's *generated PostgreSQL* output actually contain)
    # is true independent of whether --verify can exercise it yet.
    "mysql_enum_type": NOT_VERIFIABLE,  # rewritten to a synthesized <table>_<column>_t type reference; ENUM(...) itself never survives
    "mysql_on_update_current_timestamp": VERBATIM,  # ON UPDATE CURRENT_TIMESTAMP is copied straight into the generated DEFAULT
    "mysql_on_duplicate_key_update": VERBATIM,  # the whole ON DUPLICATE KEY UPDATE clause is copied unchanged into the function body
    "mysql_signal": VERBATIM,  # SIGNAL/RESIGNAL is copied unchanged (only the SET keyword before MESSAGE_TEXT is lost)
    "mysql_fulltext_index": VERBATIM,  # 'FULLTEXT KEY'/'FULLTEXT INDEX' is left sitting in the output, case-folded but keyword-intact
    "mysql_key_index": VERBATIM,  # the bare 'key <NAME>' stub survives in the output where a column was expected
    "mysql_spatial_index": VERBATIM,  # same shape as fulltext: 'spatial KEY' left in the column list
    "mysql_limit_comma": VERBATIM,  # `LIMIT n, m` copied straight into the function body
    "mysql_replace_into": VERBATIM,  # REPLACE INTO copied unchanged into the function body
    "mysql_insert_ignore": VERBATIM,  # INSERT IGNORE copied unchanged into the function body
    "mysql_prepare_from": VERBATIM,  # `PREPARE <name> FROM` copied unchanged (only the @var becomes a plain variable)
    "mysql_last_insert_id": VERBATIM,  # the LAST_INSERT_ID() call is copied unchanged
    "mysql_auto_increment_start": NOT_VERIFIABLE,  # a table option that is dropped; AUTO_INCREMENT=<n> is never in the output by construction
    "mysql_date_format": NOT_VERIFIABLE,  # rewritten into a row constructor; the DATE_FORMAT name never survives
    "mysql_foreign_key": NOT_VERIFIABLE,  # dropped entirely -- no FOREIGN KEY reaches the output at all
    "mysql_zero_date": NOT_VERIFIABLE,  # silently rewritten to '1970-01-01'; the zero-date literal never survives
    "mysql_declare_handler": NOT_VERIFIABLE,  # dropped entirely, replaced by blank lines
    "mysql_collate": NOT_VERIFIABLE,  # the COLLATE/CHARACTER SET clause is dropped from the column definition
    "mysql_set_type": NOT_VERIFIABLE,  # rewritten to plain `text`; the SET(...) spelling never survives
    # MSSQL dialect detectors -- like the MySQL ones above, --verify
    # doesn't accept --dialect mssql yet, so none of these are reachable
    # through it today; classified here because doctor.py requires an
    # entry per detector and the classification is true regardless.
    "mssql_bracket_identifier": VERBATIM,  # the brackets survive into the generated identifier, which is exactly the problem
    "mssql_newid_default": NOT_VERIFIABLE,  # rewritten to uuid_generate_v4(); the NEWID() spelling never survives
    "mssql_update_set": NOT_VERIFIABLE,  # the SET keyword is deleted by the conversion, so the source shape is gone
    "mssql_identity_column": NOT_VERIFIABLE,  # IDENTITY is dropped entirely; nothing of it reaches the output
    "mssql_parameterless_procedure": NOT_VERIFIABLE,  # the finding is about the generated DECLARE block, not a surviving source token
    "mssql_if_statement": VERBATIM,  # the IF survives (mis-closed or without THEN), so re-detection is meaningful
    "mssql_raiserror": VERBATIM,  # RAISERROR/THROW are copied unchanged
    "mssql_try_catch": VERBATIM,  # the whole TRY/CATCH construct is copied unchanged
    "mssql_top_clause": VERBATIM,  # TOP n is copied unchanged
    "mssql_scope_identity": VERBATIM,  # the call is copied unchanged
    "mssql_output_clause": VERBATIM,  # the OUTPUT clause is copied unchanged
    "mssql_iif": VERBATIM,  # the IIF call is copied unchanged
    "mssql_datediff": VERBATIM,  # the DATEDIFF call is copied unchanged
    "mssql_charindex": NOT_VERIFIABLE,  # rewritten into position(); the CHARINDEX name never survives
    "mssql_filtered_index": NOT_VERIFIABLE,  # the whole CREATE INDEX statement is dropped
    "mssql_foreign_key": NOT_VERIFIABLE,  # dropped entirely -- no FOREIGN KEY reaches the output at all
    "mssql_collation": NOT_VERIFIABLE,  # the COLLATE clause is dropped and the column becomes citext
    "mssql_computed_column": NOT_VERIFIABLE,  # rewritten into a trigger; the `AS (expr)` column syntax never survives
    "mssql_rowversion": NOT_VERIFIABLE,  # rewritten to bytea; the ROWVERSION name never survives
    # GENERATED_ONLY -- already only ever analyzes generated output
    # (--check-connect-by); no pre-migration Oracle-side finding exists
    # for verify to compare against.
    "connect_by": GENERATED_ONLY,
}


@dataclasses.dataclass(frozen=True)
class DetectorVerification:
    detector: str
    gap_number: str | None
    baseline_count: int
    post_migration_count: int
    status: str  # "still_present" | "not_detected" | "not_verifiable"


def verify_against_baseline(
    baseline: list[dict], post_migration_findings: list[Finding]
) -> list[DetectorVerification]:
    """One entry per distinct detector present in `baseline` (the loaded
    --save snapshot from the pre-migration scan) -- not one entry per
    individual finding. Matching at finding granularity (file/object/
    snippet, the way baseline.py's own NEW/RESOLVED/UNCHANGED diff works)
    doesn't survive the Oracle-to-PostgreSQL boundary: ora2pg routinely
    renames objects (autonomous_tx's own dblink strategy renames the
    procedure to *_atx) and the file is a different file entirely. The
    detector itself is the one thing guaranteed stable across that
    boundary.

    `post_migration_findings` should come from scanning ora2pg's
    generated PostgreSQL output with the same detectors (scan_source()),
    not the original Oracle source."""
    post_migration_counts: dict[str, int] = {}
    for f in post_migration_findings:
        post_migration_counts[f.detector] = post_migration_counts.get(f.detector, 0) + 1

    baseline_counts: dict[str, int] = {}
    for rec in baseline:
        detector = rec["detector"]
        baseline_counts[detector] = baseline_counts.get(detector, 0) + 1

    results = []
    for detector in sorted(baseline_counts):
        mode = VERIFICATION_MODE.get(detector, NOT_VERIFIABLE)
        gap = gap_by_detector(detector)
        post_count = post_migration_counts.get(detector, 0)

        if mode != VERBATIM:
            status = "not_verifiable"
        elif post_count > 0:
            status = "still_present"
        else:
            status = "not_detected"

        results.append(
            DetectorVerification(
                detector=detector,
                gap_number=gap.number if gap is not None else None,
                baseline_count=baseline_counts[detector],
                post_migration_count=post_count,
                status=status,
            )
        )
    return results
