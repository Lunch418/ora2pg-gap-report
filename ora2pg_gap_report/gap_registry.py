"""Canonical GAP-NNN registry data: the mapping between the human-facing
gap numbers used in docs/research/ and docs/research/GAP_REGISTRY.md, and
the actual code (detector module, test files) that implements and
verifies each one.

This mapping didn't exist anywhere as data before this module: a Finding
never carries a "GAP-023"-style number at all (see cli.py -- a
detector's own identity is a plain string like "oracle_text", not a gap
number), and the only other place enumerating the 28 rows was
scripts/audit_gap_test_counts.py's own private, hand-maintained list.
That script now imports GAPS from here instead of keeping a second copy
in sync by hand -- exactly the kind of registry/detector/test drift this
project's own AUDIT.md review rounds kept finding manually is the thing
a second hand-maintained list invites.

Note on packaging: this module ships inside the installed package (it's
needed by --explain, an ordinary CLI flag), but docs/research/ itself
does NOT -- see pyproject.toml's [tool.setuptools.packages.find], which
only packages ora2pg_gap_report*. research_doc_path() returns None
gracefully when the repo's docs/ isn't actually there (a pip install,
not a source checkout); callers are expected to fall back to a GitHub
link built from `slug`, which this module always has independent of
whether any file exists on disk."""

import dataclasses
import re
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent


@dataclasses.dataclass(frozen=True)
class GapEntry:
    number: str  # "001".."028", always 3 digits
    detector: str  # matches Finding.detector and detectors/<name>.py
    slug: str  # matches docs/research/gap-<number>-<slug>.md
    test_files: tuple[str, ...]
    # "high" | "medium" | "low" -- must match the literal `severity=` value
    # every Finding this detector emits actually uses (checked one way: the
    # detector's own source only ever uses one such literal throughout the
    # whole file, verified by hand before this field existed; checked the
    # other way, ongoing: scripts/doctor.py greps the detector's source for
    # every `severity="..."` literal and fails the build if that set isn't
    # exactly {this value} -- the same drift-prevention pattern as
    # ora2pg_version/postgresql_version/failure_stage below, just for the
    # one gap-level fact that had never been centralized at all before this).
    severity: str
    # Every gap confirmed in this registry so far was reproduced against
    # exactly these two versions (see docs/research/AUDIT.md's blanket
    # statement) -- defaults, not hardcoded per-entry, specifically so a
    # future gap confirmed on a different version doesn't require touching
    # all 28 existing entries, just overriding these two fields on its own
    # GapEntry. Not "these versions still work today" (never re-verified),
    # only "this is what was actually run when the finding was confirmed" --
    # see docs/research/GAP_REGISTRY.md and each gap's own doc for the
    # underlying evidence this restates in machine-readable form.
    ora2pg_version: str = "25.0"
    postgresql_version: str = "16"
    # When, concretely, would someone actually notice this gap -- one of
    # FAILURE_STAGES below, or None for the two gaps in
    # FAILURE_STAGE_EXEMPT_DETECTORS. Every other gap has a value taken
    # directly from its own research doc's "Наблюдаемая проблема" section
    # (not guessed) -- see docs/failure-stage-notes.md for the trial batch
    # that validated the taxonomy before the full rollout, and for why
    # "conversion" is defined but, as it turned out, unused by any of the
    # 37. scripts/doctor.py enforces both: a *set* value must be one of
    # FAILURE_STAGES, and every gap not in FAILURE_STAGE_EXEMPT_DETECTORS
    # must have one set.
    failure_stage: str | None = None
    # Which source language ora2pg was pointed at to produce the finding
    # -- "oracle" (the default, so this field stayed a pure addition when
    # it was introduced, not a migration), "mysql" (ora2pg -m) or
    # "mssql" (ora2pg -M). Both non-Oracle dialects were confirmed to
    # work file-based via -i exactly like Oracle mode -- no live
    # MySQL/SQL Server connection is needed to reproduce any gap here.
    # One registry, one numbering sequence, one CLI, one set of report
    # formats: the dialect is a fact about a gap, the same kind of fact
    # severity or failure_stage already is, not a reason to fork the
    # project into separate per-dialect tools. Note the sequence is
    # deliberately continuous across dialects rather than prefixed
    # per-dialect -- scripts/doctor.py anchors on a plain \\d{3} in
    # several places, and research_doc_path() builds
    # gap-{number}-{slug}.md, so continuing the numbering costs nothing
    # while a GAP-MY-/GAP-MS- scheme would have touched all of it.
    dialect: str = "oracle"
    # The date this gap's finding was actually recorded against a real
    # ora2pg run, as ISO yyyy-mm-dd -- taken from when its research doc
    # was written, which is the record of that run. Not "still true
    # today": nothing here is re-verified automatically, and
    # ora2pg_version above says which ora2pg it was true of. The pair
    # matters together, and cli.py warns when the installed ora2pg is a
    # different version from the one a finding is being reported against.
    # No default on purpose -- a gap without a verification date would be
    # a claim with no evidence behind it, and defaulting one in would
    # make that invisible. kw_only so a required field can still follow
    # the defaulted ones above without reordering the four positional
    # arguments every entry already passes (Python 3.10+, which this
    # project requires).
    last_verified: str = dataclasses.field(kw_only=True)

    # Deliberately NOT here: verification.py's VERIFICATION_MODE, and
    # messages.py's MESSAGES/REMEDIATION_HINTS. They are keyed by
    # detector, and detectors outnumber gaps -- dbms_utl_calls is a
    # classifier with no GAP-NNN of its own. Pulling them in would mean
    # inventing a gap for it or special-casing it out, and a registry
    # with one documented exception is what drifts. See verification.py's
    # own "Why this isn't a GapEntry field".


# "conversion": only visible in ora2pg's own conversion run/log (a debug
#   line, or an omitted/undercounted object) -- no gap in the registry
#   actually landed here (see docs/failure-stage-notes.md), kept defined
#   in case a future gap does.
# "deployment": the generated DDL itself fails to load into PostgreSQL,
#   immediately -- CREATE TABLE/TYPE/SEQUENCE and similar, outside any
#   function/procedure body (with one exception: connect_by_nocycle's own
#   research doc confirms its CREATE PROCEDURE itself fails at load time,
#   not deferred -- see its "Наблюдаемая проблема").
# "runtime": the DDL loads cleanly -- ora2pg's own generated dump sets
#   `check_function_bodies = false`, so a syntax error inside a function/
#   procedure/trigger body is deferred -- but the flagged code fails the
#   first time it actually runs.
# "semantic": nothing ever raises an error, at any stage. Behavior is
#   just silently different from Oracle, forever, unless someone
#   specifically goes looking for it.
def verified_ora2pg_versions() -> frozenset[str]:
    """Every ora2pg version any gap in the registry was confirmed against.

    A set rather than one value because nothing forces the registry to be
    single-version -- ora2pg_version is per-gap precisely so a gap
    confirmed on a later release doesn't require restating the other 104.
    Today they all share one value; a caller comparing an installed
    version against this must handle more.
    """
    return frozenset(gap.ora2pg_version for gap in GAPS)


FAILURE_STAGES = ("conversion", "deployment", "runtime", "semantic")

# The only two gaps whose finding isn't about a code-shape/runtime problem
# at all -- both are about ora2pg's own cost-estimation output
# (SHOW_REPORT/--estimate_cost) being wrong or absent, not about anything
# that fails or behaves differently once actually run. See each one's own
# inline comment in GAPS below, and verification.py's matching special-
# case treatment of autonomous_tx for the same underlying reason.
FAILURE_STAGE_EXEMPT_DETECTORS = frozenset({"autonomous_tx", "object_type"})


GAPS: tuple[GapEntry, ...] = (
    # autonomous_tx: failure_stage left unset deliberately, not an
    # oversight -- its finding is about SHOW_REPORT/--estimate_cost
    # underestimating migration *cost*, not about broken generated code,
    # same reason it's a verification.py special case (see that module's
    # own comment on this detector).
    GapEntry("001", "autonomous_tx", "autonomous-transaction", ("test_autonomous_tx.py", "test_autonomous_tx_edge_cases.py"), severity="high", last_verified="2026-08-14"),
    GapEntry("002", "merge_delete_clause", "merge-delete-clause", ("test_merge_delete_clause.py",), severity="high", failure_stage="runtime", last_verified="2026-08-14"),
    GapEntry("003", "bulk_collect", "bulk-collect-forall", ("test_bulk_collect.py",), severity="high", failure_stage="runtime", last_verified="2026-08-14"),
    GapEntry(
        "004", "compound_triggers", "compound-trigger", ("test_compound_triggers.py",), severity="high", failure_stage="semantic", last_verified="2026-08-14"),
    GapEntry("005", "connect_by", "connect-by-level", ("test_connect_by.py",), severity="high", failure_stage="runtime", last_verified="2026-08-14"),
    GapEntry("006", "database_link", "database-link", ("test_database_link.py",), severity="high", failure_stage="runtime", last_verified="2026-08-14"),
    GapEntry("007", "model_clause", "model-clause", ("test_model_clause.py",), severity="high", failure_stage="runtime", last_verified="2026-08-14"),
    GapEntry("008", "pivot_clause", "pivot-unpivot", ("test_pivot_clause.py",), severity="high", failure_stage="runtime", last_verified="2026-08-14"),
    # object_type: failure_stage left unset for the same class of reason
    # as autonomous_tx -- its finding is that --estimate_cost/SHOW_REPORT
    # returns *no* number at all for TYPE objects (not a broken/silent
    # runtime behavior), see docs/research/gap-009-object-type.md.
    GapEntry("009", "object_type", "object-type", ("test_object_type.py",), severity="high", last_verified="2026-08-14"),
    GapEntry("010", "with_function", "with-function", ("test_with_function.py",), severity="high", failure_stage="runtime", last_verified="2026-08-14"),
    GapEntry("011", "flashback_query", "flashback-query", ("test_flashback_query.py",), severity="high", failure_stage="runtime", last_verified="2026-08-14"),
    GapEntry("012", "global_temp_table", "global-temp-table", ("test_global_temp_table.py",), severity="high", failure_stage="semantic", last_verified="2026-08-15"),
    GapEntry("013", "table_partitioning", "table-partitioning", ("test_table_partitioning.py",), severity="high", failure_stage="semantic", last_verified="2026-08-15"),
    GapEntry("014", "connect_by_nocycle", "connect-by-nocycle", ("test_connect_by_nocycle.py",), severity="high", failure_stage="deployment", last_verified="2026-08-15"),
    GapEntry("015", "context_object", "context", ("test_context_object.py",), severity="medium", failure_stage="semantic", last_verified="2026-08-15"),
    GapEntry("016", "insert_all", "insert-all", ("test_insert_all.py",), severity="high", failure_stage="runtime", last_verified="2026-08-15"),
    GapEntry("017", "json_table", "json-table", ("test_json_table.py",), severity="high", failure_stage="runtime", last_verified="2026-08-15"),
    GapEntry("018", "external_table", "external-table", ("test_external_table.py",), severity="high", failure_stage="semantic", last_verified="2026-08-15"),
    GapEntry("019", "sql_macro", "sql-macro", ("test_sql_macro.py",), severity="high", failure_stage="runtime", last_verified="2026-08-15"),
    GapEntry("020", "invisible_column", "invisible-column", ("test_invisible_column.py",), severity="high", failure_stage="semantic", last_verified="2026-08-15"),
    GapEntry(
        "021", "collection_type", "collection-type", ("test_collection_type.py",), severity="high", failure_stage="deployment", last_verified="2026-08-15"),
    GapEntry("022", "cross_apply", "cross-apply", ("test_cross_apply.py",), severity="high", failure_stage="runtime", last_verified="2026-08-15"),
    GapEntry("023", "oracle_text", "oracle-text", ("test_oracle_text.py",), severity="high", failure_stage="runtime", last_verified="2026-08-15"),
    GapEntry("024", "recursive_with", "recursive-with", ("test_recursive_with.py",), severity="high", failure_stage="runtime", last_verified="2026-08-15"),
    GapEntry("025", "invisible_index", "invisible-index", ("test_invisible_index.py",), severity="medium", failure_stage="semantic", last_verified="2026-08-15"),
    GapEntry(
        "026", "read_only_table", "read-only-table", ("test_read_only_table.py",), severity="high", failure_stage="semantic", last_verified="2026-08-15"),
    GapEntry("027", "materialized_view_log", "materialized-view-log", ("test_materialized_view_log.py",), severity="high", failure_stage="semantic", last_verified="2026-08-15"),
    GapEntry(
        "028", "identity_column", "identity-column", ("test_identity_column.py",), severity="high", failure_stage="deployment", last_verified="2026-08-15"),
    GapEntry("029", "rowid_type", "rowid-urowid", ("test_rowid_type.py",), severity="high", failure_stage="runtime", last_verified="2026-08-17"),
    GapEntry("030", "sequence_cycle", "sequence-cycle", ("test_sequence_cycle.py",), severity="high", failure_stage="runtime", last_verified="2026-08-17"),
    GapEntry(
        "031", "default_on_null", "default-on-null", ("test_default_on_null.py",), severity="high", failure_stage="deployment", last_verified="2026-08-17"),
    GapEntry("032", "public_synonym", "public-synonym", ("test_public_synonym.py",), severity="high", failure_stage="deployment", last_verified="2026-08-17"),
    GapEntry(
        "033", "virtual_column", "virtual-column", ("test_virtual_column.py",), severity="medium", failure_stage="semantic", last_verified="2026-08-17"),
    GapEntry("034", "nested_subprogram", "nested-subprogram", ("test_nested_subprogram.py",), severity="high", failure_stage="runtime", last_verified="2026-08-17"),
    GapEntry(
        "035",
        "conditional_compilation",
        "conditional-compilation",
        ("test_conditional_compilation.py",),
        severity="high", failure_stage="runtime", last_verified="2026-08-17"),
    GapEntry("036", "package_state", "package-state", ("test_package_state.py",), severity="high", failure_stage="runtime", last_verified="2026-08-17"),
    GapEntry(
        "037",
        "index_organized_table",
        "index-organized-table",
        ("test_index_organized_table.py",),
        severity="medium", failure_stage="semantic", last_verified="2026-08-17"),
GapEntry(
        "038", "match_recognize", "match-recognize", ("test_match_recognize.py",), severity="high", failure_stage="deployment", last_verified="2026-08-27"),
    GapEntry(
        "039",
        "connect_by_pseudocolumn",
        "connect-by-pseudocolumn",
        ("test_connect_by_pseudocolumn.py",),
        severity="high",
        failure_stage="deployment", last_verified="2026-08-27"),
    GapEntry(
        "040", "keep_dense_rank", "keep-dense-rank", ("test_keep_dense_rank.py",), severity="high", failure_stage="deployment", last_verified="2026-08-27"),
    GapEntry(
        "041", "multiset_operator", "multiset-operator", ("test_multiset_operator.py",), severity="high", failure_stage="deployment", last_verified="2026-08-27"),
    GapEntry(
        "042", "sample_clause", "sample-clause", ("test_sample_clause.py",), severity="high", failure_stage="deployment", last_verified="2026-08-27"),
    GapEntry(
        "043", "accessible_by", "accessible-by", ("test_accessible_by.py",), severity="high", failure_stage="deployment", last_verified="2026-08-27"),
    GapEntry(
        "044", "local_time_zone", "local-time-zone", ("test_local_time_zone.py",), severity="high", failure_stage="semantic", last_verified="2026-08-27"),
    GapEntry(
        "045", "temporal_validity", "temporal-validity", ("test_temporal_validity.py",), severity="high", failure_stage="deployment", last_verified="2026-08-27"),
    GapEntry(
        "046", "bitmap_index", "bitmap-index", ("test_bitmap_index.py",), severity="high", failure_stage="deployment", last_verified="2026-08-27"),
    GapEntry(
        "047", "object_table", "object-table", ("test_object_table.py",), severity="high", failure_stage="semantic", last_verified="2026-08-27"),
    GapEntry(
        "048", "ignore_nulls", "ignore-nulls", ("test_ignore_nulls.py",), severity="high", failure_stage="deployment", last_verified="2026-08-28"),
    GapEntry("049", "nlssort", "nlssort", ("test_nlssort.py",), severity="high", failure_stage="deployment", last_verified="2026-08-28"),
    GapEntry(
        "050", "long_raw_type", "long-raw-type", ("test_long_raw_type.py",), severity="high", failure_stage="runtime", last_verified="2026-08-28"),
    GapEntry(
        "051", "anydata_type", "anydata-type", ("test_anydata_type.py",), severity="high", failure_stage="deployment", last_verified="2026-08-28"),
    GapEntry(
        "052", "system_trigger", "system-trigger", ("test_system_trigger.py",), severity="high", failure_stage="deployment", last_verified="2026-08-28"),
    # trigger_follows: "runtime", not "deployment" -- the clause lands
    # *inside* the generated function body, so check_function_bodies=false
    # defers it past CREATE FUNCTION/CREATE TRIGGER and it only breaks on
    # the first row the trigger fires for. Confirmed that way round by a
    # real INSERT, not assumed (see the gap's own research doc).
    GapEntry(
        "053", "trigger_follows", "trigger-follows", ("test_trigger_follows.py",), severity="high", failure_stage="runtime", last_verified="2026-08-28"),
    GapEntry(
        "054", "table_collection", "table-collection", ("test_table_collection.py",), severity="high", failure_stage="deployment", last_verified="2026-08-28"),
    GapEntry(
        "055", "cursor_expression", "cursor-expression", ("test_cursor_expression.py",), severity="high", failure_stage="deployment", last_verified="2026-08-28"),
    GapEntry(
        "056", "for_update_wait", "for-update-wait", ("test_for_update_wait.py",), severity="high", failure_stage="deployment", last_verified="2026-08-28"),
    GapEntry(
        "057", "rownum_dml", "rownum-dml", ("test_rownum_dml.py",), severity="high", failure_stage="deployment", last_verified="2026-08-28"),
    GapEntry(
        "058", "to_date_rr", "to-date-rr", ("test_to_date_rr.py",), severity="high", failure_stage="semantic", last_verified="2026-08-28"),
    # authid_clause: the first and so far only gap whose failure_stage is
    # "conversion" -- the stage FAILURE_STAGES has defined since the
    # taxonomy was introduced but which nothing had ever landed in (see
    # docs/failure-stage-notes.md). Nothing fails at deploy or run time
    # because the routine never reaches the output at all.
    GapEntry(
        "059", "authid_clause", "authid-clause", ("test_authid_clause.py",), severity="high", failure_stage="conversion", last_verified="2026-08-28"),
    GapEntry(
        "060", "pragma_exception_init", "pragma-exception-init", ("test_pragma_exception_init.py",), severity="high", failure_stage="runtime", last_verified="2026-08-28"),
    GapEntry(
        "061", "subtype_range", "subtype-range", ("test_subtype_range.py",), severity="high", failure_stage="deployment", last_verified="2026-08-28"),
    GapEntry(
        "062", "alt_quote_literal", "alt-quote-literal", ("test_alt_quote_literal.py",), severity="high", failure_stage="runtime", last_verified="2026-08-28"),
    GapEntry(
        "063", "goto_statement", "goto-statement", ("test_goto_statement.py",), severity="high", failure_stage="runtime", last_verified="2026-08-28"),
    GapEntry(
        "064", "cursor_rowtype", "cursor-rowtype", ("test_cursor_rowtype.py",), severity="high", failure_stage="runtime", last_verified="2026-08-28"),
    GapEntry("065", "wm_concat", "wm-concat", ("test_wm_concat.py",), severity="high", failure_stage="runtime", last_verified="2026-08-28"),
    GapEntry(
        "066", "read_only_view", "read-only-view", ("test_read_only_view.py",), severity="high", failure_stage="semantic", last_verified="2026-08-28"),
    # sdo_geometry: the only "medium" of this batch -- ora2pg picks the
    # right target type (PostGIS geometry) and merely omits the
    # CREATE EXTENSION line it needs, so one line fixes it, unlike the
    # rest of the batch where the construct has to be rewritten.
    GapEntry(
        "067", "sdo_geometry", "sdo-geometry", ("test_sdo_geometry.py",), severity="medium", failure_stage="deployment", last_verified="2026-08-28"),
    # First MySQL-dialect batch (ora2pg -m), same numbering sequence as
    # every Oracle gap above it -- see GapEntry.dialect's own comment for
    # why this project uses one registry/one sequence rather than
    # forking numbering per source language. All five reproduced against
    # the exact same ora2pg 25.0 + PostgreSQL 16 pair as the Oracle
    # batch, confirmed file-based via `ora2pg -m -i <file>` (no live
    # MySQL connection needed, exactly like Oracle mode's `-t <TYPE> -i
    # <file>`).
    GapEntry(
        "068",
        "mysql_enum_type",
        "mysql-enum-type",
        ("test_mysql_enum_type.py",),
        severity="high",
        failure_stage="deployment",
        dialect="mysql", last_verified="2026-09-01"),
    GapEntry(
        "069",
        "mysql_on_update_current_timestamp",
        "mysql-on-update-current-timestamp",
        ("test_mysql_on_update_current_timestamp.py",),
        severity="high",
        failure_stage="deployment",
        dialect="mysql", last_verified="2026-09-01"),
    GapEntry(
        "070",
        "mysql_on_duplicate_key_update",
        "mysql-on-duplicate-key-update",
        ("test_mysql_on_duplicate_key_update.py",),
        severity="high",
        failure_stage="runtime",
        dialect="mysql", last_verified="2026-09-01"),
    GapEntry(
        "071",
        "mysql_signal",
        "mysql-signal",
        ("test_mysql_signal.py",),
        severity="high",
        failure_stage="runtime",
        dialect="mysql", last_verified="2026-09-01"),
    GapEntry(
        "072",
        "mysql_fulltext_index",
        "mysql-fulltext-index",
        ("test_mysql_fulltext_index.py",),
        severity="high",
        failure_stage="deployment",
        dialect="mysql", last_verified="2026-09-01"),
    # Second MySQL batch. Two things this batch made visible that the
    # first one didn't: ora2pg's MySQL side breaks on constructs that are
    # not exotic at all (a bare KEY index clause is what mysqldump emits
    # by default for every secondary index), and several of its failures
    # never raise an error at any stage -- hence the first cluster of
    # failure_stage="semantic" gaps in this registry (081..086).
    GapEntry(
        "073",
        "mysql_key_index",
        "mysql-key-index",
        ("test_mysql_key_index.py",),
        severity="high",
        failure_stage="deployment",
        dialect="mysql", last_verified="2026-09-01"),
    GapEntry(
        "074",
        "mysql_spatial_index",
        "mysql-spatial-index",
        ("test_mysql_spatial_index.py",),
        severity="high",
        failure_stage="deployment",
        dialect="mysql", last_verified="2026-09-01"),
    GapEntry(
        "075",
        "mysql_limit_comma",
        "mysql-limit-comma",
        ("test_mysql_limit_comma.py",),
        severity="high",
        failure_stage="runtime",
        dialect="mysql", last_verified="2026-09-01"),
    GapEntry(
        "076",
        "mysql_replace_into",
        "mysql-replace-into",
        ("test_mysql_replace_into.py",),
        severity="high",
        failure_stage="runtime",
        dialect="mysql", last_verified="2026-09-01"),
    GapEntry(
        "077",
        "mysql_insert_ignore",
        "mysql-insert-ignore",
        ("test_mysql_insert_ignore.py",),
        severity="high",
        failure_stage="runtime",
        dialect="mysql", last_verified="2026-09-01"),
    GapEntry(
        "078",
        "mysql_prepare_from",
        "mysql-prepare-from",
        ("test_mysql_prepare_from.py",),
        severity="high",
        failure_stage="runtime",
        dialect="mysql", last_verified="2026-09-01"),
    GapEntry(
        "079",
        "mysql_last_insert_id",
        "mysql-last-insert-id",
        ("test_mysql_last_insert_id.py",),
        severity="high",
        failure_stage="runtime",
        dialect="mysql", last_verified="2026-09-01"),
    # auto_increment_start is "runtime" rather than "semantic" on purpose:
    # nothing errors while the schema loads, but the very first INSERT
    # after the data is migrated fails on the primary key -- a real
    # error at a specific moment, not a silent divergence.
    GapEntry(
        "080",
        "mysql_auto_increment_start",
        "mysql-auto-increment-start",
        ("test_mysql_auto_increment_start.py",),
        severity="high",
        failure_stage="runtime",
        dialect="mysql", last_verified="2026-09-01"),
    GapEntry(
        "081",
        "mysql_date_format",
        "mysql-date-format",
        ("test_mysql_date_format.py",),
        severity="high",
        failure_stage="semantic",
        dialect="mysql", last_verified="2026-09-01"),
    GapEntry(
        "082",
        "mysql_foreign_key",
        "mysql-foreign-key",
        ("test_mysql_foreign_key.py",),
        severity="high",
        failure_stage="semantic",
        dialect="mysql", last_verified="2026-09-01"),
    GapEntry(
        "083",
        "mysql_zero_date",
        "mysql-zero-date",
        ("test_mysql_zero_date.py",),
        severity="high",
        failure_stage="semantic",
        dialect="mysql", last_verified="2026-09-01"),
    GapEntry(
        "084",
        "mysql_declare_handler",
        "mysql-declare-handler",
        ("test_mysql_declare_handler.py",),
        severity="high",
        failure_stage="semantic",
        dialect="mysql", last_verified="2026-09-01"),
    GapEntry(
        "085",
        "mysql_collate",
        "mysql-collate",
        ("test_mysql_collate.py",),
        severity="high",
        failure_stage="semantic",
        dialect="mysql", last_verified="2026-09-01"),
    # mysql_set_type: the one medium of this batch. Unlike ENUM
    # (GAP-068), which breaks the schema load outright, SET converts into
    # a working text column, existing values survive verbatim, and
    # nothing ever returns a wrong answer -- what's lost is validation of
    # future writes, which is a CHECK constraint away.
    GapEntry(
        "086",
        "mysql_set_type",
        "mysql-set-type",
        ("test_mysql_set_type.py",),
        severity="medium",
        failure_stage="semantic",
        dialect="mysql", last_verified="2026-09-01"),
    # MSSQL (T-SQL / SQL Server) batch, ora2pg -M. Two findings shape
    # this whole set. First, the file-based path (-M -i <file>) never
    # strips T-SQL's bracket-quoted identifiers, which SSMS emits for
    # every name, so GAP-087 alone takes down essentially any real
    # script before the rest even get a chance to matter. Second, a
    # plain UPDATE ... SET (GAP-089) and a parameterless procedure
    # (GAP-091) are both mis-converted, and neither is an exotic
    # construct -- which is why this dialect's confirmed set skews so
    # heavily toward "every routine in the file" rather than "one rare
    # feature".
    GapEntry(
        "087",
        "mssql_bracket_identifier",
        "mssql-bracket-identifier",
        ("test_mssql_bracket_identifier.py",),
        severity="high",
        failure_stage="deployment",
        dialect="mssql", last_verified="2026-09-01"),
    GapEntry(
        "088",
        "mssql_newid_default",
        "mssql-newid-default",
        ("test_mssql_newid_default.py",),
        severity="high",
        failure_stage="deployment",
        dialect="mssql", last_verified="2026-09-01"),
    GapEntry(
        "089",
        "mssql_update_set",
        "mssql-update-set",
        ("test_mssql_update_set.py",),
        severity="high",
        failure_stage="runtime",
        dialect="mssql", last_verified="2026-09-01"),
    GapEntry(
        "090",
        "mssql_identity_column",
        "mssql-identity-column",
        ("test_mssql_identity_column.py",),
        severity="high",
        failure_stage="runtime",
        dialect="mssql", last_verified="2026-09-01"),
    GapEntry(
        "091",
        "mssql_parameterless_procedure",
        "mssql-parameterless-procedure",
        ("test_mssql_parameterless_procedure.py",),
        severity="high",
        failure_stage="runtime",
        dialect="mssql", last_verified="2026-09-01"),
    GapEntry(
        "092",
        "mssql_if_statement",
        "mssql-if-statement",
        ("test_mssql_if_statement.py",),
        severity="high",
        failure_stage="runtime",
        dialect="mssql", last_verified="2026-09-01"),
    GapEntry(
        "093",
        "mssql_raiserror",
        "mssql-raiserror",
        ("test_mssql_raiserror.py",),
        severity="high",
        failure_stage="runtime",
        dialect="mssql", last_verified="2026-09-01"),
    GapEntry(
        "094",
        "mssql_try_catch",
        "mssql-try-catch",
        ("test_mssql_try_catch.py",),
        severity="high",
        failure_stage="runtime",
        dialect="mssql", last_verified="2026-09-01"),
    GapEntry(
        "095",
        "mssql_top_clause",
        "mssql-top-clause",
        ("test_mssql_top_clause.py",),
        severity="high",
        failure_stage="runtime",
        dialect="mssql", last_verified="2026-09-01"),
    GapEntry(
        "096",
        "mssql_scope_identity",
        "mssql-scope-identity",
        ("test_mssql_scope_identity.py",),
        severity="high",
        failure_stage="runtime",
        dialect="mssql", last_verified="2026-09-01"),
    GapEntry(
        "097",
        "mssql_output_clause",
        "mssql-output-clause",
        ("test_mssql_output_clause.py",),
        severity="high",
        failure_stage="runtime",
        dialect="mssql", last_verified="2026-09-01"),
    GapEntry(
        "098",
        "mssql_iif",
        "mssql-iif",
        ("test_mssql_iif.py",),
        severity="high",
        failure_stage="runtime",
        dialect="mssql", last_verified="2026-09-01"),
    GapEntry(
        "099",
        "mssql_datediff",
        "mssql-datediff",
        ("test_mssql_datediff.py",),
        severity="high",
        failure_stage="runtime",
        dialect="mssql", last_verified="2026-09-01"),
    GapEntry(
        "100",
        "mssql_charindex",
        "mssql-charindex",
        ("test_mssql_charindex.py",),
        severity="high",
        failure_stage="runtime",
        dialect="mssql", last_verified="2026-09-01"),
    GapEntry(
        "101",
        "mssql_filtered_index",
        "mssql-filtered-index",
        ("test_mssql_filtered_index.py",),
        severity="high",
        failure_stage="semantic",
        dialect="mssql", last_verified="2026-09-01"),
    GapEntry(
        "102",
        "mssql_foreign_key",
        "mssql-foreign-key",
        ("test_mssql_foreign_key.py",),
        severity="high",
        failure_stage="semantic",
        dialect="mssql", last_verified="2026-09-01"),
    GapEntry(
        "103",
        "mssql_collation",
        "mssql-collation",
        ("test_mssql_collation.py",),
        severity="high",
        failure_stage="semantic",
        dialect="mssql", last_verified="2026-09-01"),
    GapEntry(
        "104",
        "mssql_computed_column",
        "mssql-computed-column",
        ("test_mssql_computed_column.py",),
        severity="high",
        failure_stage="semantic",
        dialect="mssql", last_verified="2026-09-01"),
    GapEntry(
        "105",
        "mssql_rowversion",
        "mssql-rowversion",
        ("test_mssql_rowversion.py",),
        severity="high",
        failure_stage="semantic",
        dialect="mssql", last_verified="2026-09-01"),
)

_BY_NUMBER = {g.number: g for g in GAPS}
_BY_DETECTOR = {g.detector: g for g in GAPS}

_GAP_REF_RE = re.compile(r"^(?:GAP-?)?(\d{1,3})$", re.IGNORECASE)


def normalize_gap_number(raw: str) -> str | None:
    """'GAP-023', 'gap23', '023', '23' -> '023'. None if `raw` isn't
    recognizable as a gap reference at all (caller distinguishes that
    from "well-formed number, but no such gap" via gap_by_number()
    returning None)."""
    m = _GAP_REF_RE.match(raw.strip())
    return m.group(1).zfill(3) if m else None


def gap_by_number(number: str) -> GapEntry | None:
    return _BY_NUMBER.get(number)


def gap_by_detector(detector: str) -> GapEntry | None:
    return _BY_DETECTOR.get(detector)


def gap_metadata(detector: str) -> tuple[str | None, str | None]:
    """(gap_number, failure_stage) for a detector -- both None if it
    isn't a registered gap at all (e.g. dbms_utl_calls, a classifier with
    no GAP-NNN of its own; see its own comment in GAPS), and
    (gap_number, None) for the two gaps in FAILURE_STAGE_EXEMPT_DETECTORS.
    Shared by report_generator.py's --format json/csv/sarif/markdown/html
    and baseline.py's --save, so a finding's gap/stage metadata is
    computed the same way everywhere it's shown, not reimplemented per
    format."""
    gap = gap_by_detector(detector)
    if gap is None:
        return None, None
    return gap.number, gap.failure_stage


def research_doc_path(gap: GapEntry) -> Path | None:
    """Path to this gap's docs/research/gap-NNN-<slug>.md in a *source
    checkout* of the repository -- None if docs/ isn't there at all (a
    pip install; see the module docstring) or the file is genuinely
    missing."""
    path = REPO_ROOT / "docs" / "research" / f"gap-{gap.number}-{gap.slug}.md"
    return path if path.is_file() else None


def research_doc_url(gap: GapEntry) -> str:
    """A research doc's canonical GitHub URL -- always constructible
    from `slug` alone, independent of whether the file exists on the
    machine running this code."""
    return (
        "https://github.com/Lunch418/ora2pg-gap-report/blob/main/"
        f"docs/research/gap-{gap.number}-{gap.slug}.md"
    )
