"""Scan orchestration shared by cli.py (the flag-based CLI) and
tui_app.py (--tui): running every detector against a source string,
counting the objects it declares, expanding directory arguments into
files, and the opt-in CONNECT BY/ora2pg check.

Previously all five lived in cli.py itself, and tui_app.py imported them
straight from there (_connect_by_check, _expand_paths, count_objects,
scan_source, _sort_findings) -- coupling the interactive mode to the
flag-based CLI's own module instead of to a neutral layer both are peers
of. cli.py still re-exports the same names (see its own imports from this
module) so nothing about its public surface or its main()'s internal call
sites changes."""

import dataclasses
from functools import lru_cache
from pathlib import Path

from . import i18n
from .detectors.accessible_by import find_accessible_by
from .detectors.autonomous_tx import find_autonomous_transactions
from .detectors.bitmap_index import find_bitmap_indexes
from .detectors.bulk_collect import find_bulk_collect_usage
from .detectors.collection_type import find_collection_types
from .detectors.compound_triggers import find_compound_triggers
from .detectors.conditional_compilation import find_conditional_compilation
from .detectors.connect_by import find_connect_by_risks, guess_object_type, has_connect_by
from .detectors.connect_by_nocycle import find_connect_by_nocycle_or_order_siblings
from .detectors.connect_by_pseudocolumn import find_connect_by_pseudocolumns
from .detectors.context_object import find_context_declarations
from .detectors.cross_apply import find_apply_joins
from .detectors.database_link import find_database_link_references
from .detectors.dbms_utl_calls import find_dbms_utl_calls
from .detectors.default_on_null import find_default_on_null_usage
from .detectors.external_table import find_external_tables
from .detectors.flashback_query import find_flashback_queries
from .detectors.global_temp_table import find_global_temp_tables_without_delete_rows
from .detectors.identity_column import find_identity_columns_with_options
from .detectors.index_organized_table import find_index_organized_tables
from .detectors.insert_all import find_multitable_inserts
from .detectors.invisible_column import find_invisible_columns
from .detectors.invisible_index import find_invisible_indexes
from .detectors.json_table import find_json_table_calls
from .detectors.keep_dense_rank import find_keep_dense_rank
from .detectors.local_time_zone import find_local_time_zone_columns
from .detectors.match_recognize import find_match_recognize
from .detectors.materialized_view_log import find_materialized_view_logs
from .detectors.merge_delete_clause import find_merge_delete_clauses
from .detectors.model_clause import find_model_clauses
from .detectors.mssql_bracket_identifier import find_mssql_bracket_identifiers
from .detectors.mssql_charindex import find_mssql_charindex
from .detectors.mssql_collation import find_mssql_collations
from .detectors.mssql_computed_column import find_mssql_computed_columns
from .detectors.mssql_datediff import find_mssql_datediff
from .detectors.mssql_filtered_index import find_mssql_filtered_indexes
from .detectors.mssql_foreign_key import find_mssql_foreign_keys
from .detectors.mssql_identity_column import find_mssql_identity_columns
from .detectors.mssql_if_statement import find_mssql_if_statements
from .detectors.mssql_iif import find_mssql_iif
from .detectors.mssql_newid_default import find_mssql_newid_defaults
from .detectors.mssql_output_clause import find_mssql_output_clause
from .detectors.mssql_parameterless_procedure import find_mssql_parameterless_procedures
from .detectors.mssql_raiserror import find_mssql_raiserror
from .detectors.mssql_rowversion import find_mssql_rowversion_columns
from .detectors.mssql_scope_identity import find_mssql_scope_identity
from .detectors.mssql_top_clause import find_mssql_top_clause
from .detectors.mssql_try_catch import find_mssql_try_catch
from .detectors.mssql_update_set import find_mssql_update_set
from .detectors.mysql_auto_increment_start import find_mysql_auto_increment_start
from .detectors.mysql_collate import find_mysql_collations
from .detectors.mysql_date_format import find_mysql_date_format
from .detectors.mysql_declare_handler import find_mysql_declare_handlers
from .detectors.mysql_enum_type import find_mysql_enum_columns
from .detectors.mysql_foreign_key import find_mysql_foreign_keys
from .detectors.mysql_fulltext_index import find_mysql_fulltext_indexes
from .detectors.mysql_insert_ignore import find_mysql_insert_ignore
from .detectors.mysql_key_index import find_mysql_key_indexes
from .detectors.mysql_last_insert_id import find_mysql_last_insert_id
from .detectors.mysql_limit_comma import find_mysql_limit_comma
from .detectors.mysql_on_duplicate_key_update import find_mysql_on_duplicate_key_update
from .detectors.mysql_on_update_current_timestamp import find_mysql_on_update_current_timestamp
from .detectors.mysql_prepare_from import find_mysql_prepare_from
from .detectors.mysql_replace_into import find_mysql_replace_into
from .detectors.mysql_set_type import find_mysql_set_columns
from .detectors.mysql_signal import find_mysql_signal_statements
from .detectors.mysql_spatial_index import find_mysql_spatial_indexes
from .detectors.mysql_zero_date import find_mysql_zero_dates
from .detectors.multiset_operator import find_multiset_operators
from .detectors.nested_subprogram import find_nested_subprograms
from .detectors.object_table import find_object_tables
from .detectors.ignore_nulls import find_ignore_nulls
from .detectors.nlssort import find_nlssort
from .detectors.long_raw_type import find_long_raw_columns
from .detectors.anydata_type import find_anydata_columns
from .detectors.system_trigger import find_system_triggers
from .detectors.trigger_follows import find_trigger_follows
from .detectors.table_collection import find_table_collection_operator
from .detectors.cursor_expression import find_cursor_expressions
from .detectors.for_update_wait import find_for_update_wait
from .detectors.rownum_dml import find_rownum_dml
from .detectors.to_date_rr import find_to_date_rr
from .detectors.authid_clause import find_authid_clauses
from .detectors.pragma_exception_init import find_pragma_exception_init
from .detectors.subtype_range import find_subtype_ranges
from .detectors.alt_quote_literal import find_alt_quote_literals
from .detectors.goto_statement import find_goto_statements
from .detectors.cursor_rowtype import find_cursor_rowtype
from .detectors.wm_concat import find_wm_concat
from .detectors.read_only_view import find_read_only_views
from .detectors.sdo_geometry import find_sdo_geometry_columns
from .detectors.object_type import find_object_types
from .detectors.oracle_text import find_oracle_text_usage
from .detectors.package_state import find_package_state
from .detectors.pivot_clause import find_pivot_clauses
from .detectors.public_synonym import find_public_synonyms
from .detectors.read_only_table import find_read_only_tables
from .detectors.recursive_with import find_recursive_with_missing_keyword
from .detectors.rowid_type import find_rowid_types
from .detectors.sample_clause import find_sample_clauses
from .detectors.sequence_cycle import find_sequence_cycle_usage
from .detectors.sql_macro import find_sql_macros
from .detectors.table_partitioning import find_dropped_table_partitioning
from .detectors.temporal_validity import find_temporal_validity
from .detectors.virtual_column import find_virtual_columns
from .detectors.with_function import find_with_function_clauses
from .models import Finding
from .ora2pg_wrapper import Ora2PgNotFoundError, Ora2PgRunError, run_estimate_cost
from .plsql_lex import enclosing_object_name_index, mask_strings_and_comments

_ORACLE_DETECTORS = (
    find_autonomous_transactions,
    find_compound_triggers,
    find_dbms_utl_calls,
    find_merge_delete_clauses,
    find_bulk_collect_usage,
    find_database_link_references,
    find_model_clauses,
    find_pivot_clauses,
    find_object_types,
    find_with_function_clauses,
    find_flashback_queries,
    find_global_temp_tables_without_delete_rows,
    find_dropped_table_partitioning,
    find_connect_by_nocycle_or_order_siblings,
    find_context_declarations,
    find_multitable_inserts,
    find_json_table_calls,
    find_external_tables,
    find_sql_macros,
    find_invisible_columns,
    find_collection_types,
    find_apply_joins,
    find_oracle_text_usage,
    find_recursive_with_missing_keyword,
    find_invisible_indexes,
    find_read_only_tables,
    find_materialized_view_logs,
    find_identity_columns_with_options,
    find_default_on_null_usage,
    find_rowid_types,
    find_sequence_cycle_usage,
    find_public_synonyms,
    find_virtual_columns,
    find_conditional_compilation,
    find_nested_subprograms,
    find_package_state,
    find_index_organized_tables,
    find_match_recognize,
    find_connect_by_pseudocolumns,
    find_keep_dense_rank,
    find_multiset_operators,
    find_sample_clauses,
    find_accessible_by,
    find_local_time_zone_columns,
    find_temporal_validity,
    find_bitmap_indexes,
    find_object_tables,
    find_ignore_nulls,
    find_nlssort,
    find_long_raw_columns,
    find_anydata_columns,
    find_system_triggers,
    find_trigger_follows,
    find_table_collection_operator,
    find_cursor_expressions,
    find_for_update_wait,
    find_rownum_dml,
    find_to_date_rr,
    find_authid_clauses,
    find_pragma_exception_init,
    find_subtype_ranges,
    find_alt_quote_literals,
    find_goto_statements,
    find_cursor_rowtype,
    find_wm_concat,
    find_read_only_views,
    find_sdo_geometry_columns,
)
# MySQL detectors -- a source-language dialect, run against a MySQL/MariaDB
# schema/procedure dump rather than an Oracle one. Deliberately a SEPARATE
# tuple from _ORACLE_DETECTORS, not one merged list: an Oracle detector
# searches for keywords (PRAGMA, AUTHID, q'...', %ROWTYPE, PACKAGE BODY)
# that cannot appear in genuine MySQL source and vice versa, so false
# positives from cross-running them are unlikely in practice -- but
# "unlikely" is not the bar this project holds itself to (see every
# detector's own guard tests against false positives). Keeping the two
# lists separate makes that guarantee structural: a MySQL file scanned
# with dialect="oracle" and an Oracle file scanned with dialect="mysql"
# each only ever see detectors that could not possibly fire on them,
# rather than relying on every future detector's own keyword choice to
# keep staying dialect-exclusive by accident.
_MYSQL_DETECTORS = (
    find_mysql_enum_columns,
    find_mysql_on_update_current_timestamp,
    find_mysql_on_duplicate_key_update,
    find_mysql_signal_statements,
    find_mysql_fulltext_indexes,
    find_mysql_key_indexes,
    find_mysql_spatial_indexes,
    find_mysql_limit_comma,
    find_mysql_replace_into,
    find_mysql_insert_ignore,
    find_mysql_prepare_from,
    find_mysql_last_insert_id,
    find_mysql_auto_increment_start,
    find_mysql_date_format,
    find_mysql_foreign_keys,
    find_mysql_zero_dates,
    find_mysql_declare_handlers,
    find_mysql_collations,
    find_mysql_set_columns,
)
# MSSQL detectors -- the T-SQL/SQL Server source dialect (ora2pg -M),
# added on exactly the same footing as the MySQL set above and kept just
# as separate, for the same structural reason.
_MSSQL_DETECTORS = (
    find_mssql_bracket_identifiers,
    find_mssql_charindex,
    find_mssql_collations,
    find_mssql_computed_columns,
    find_mssql_datediff,
    find_mssql_filtered_indexes,
    find_mssql_foreign_keys,
    find_mssql_identity_columns,
    find_mssql_if_statements,
    find_mssql_iif,
    find_mssql_newid_defaults,
    find_mssql_output_clause,
    find_mssql_parameterless_procedures,
    find_mssql_raiserror,
    find_mssql_rowversion_columns,
    find_mssql_scope_identity,
    find_mssql_top_clause,
    find_mssql_try_catch,
    find_mssql_update_set,
)
_DETECTORS_BY_DIALECT = {
    "oracle": _ORACLE_DETECTORS,
    "mysql": _MYSQL_DETECTORS,
    "mssql": _MSSQL_DETECTORS,
}

# The single source of truth for "which dialects exist", derived from the
# detector registry above rather than typed out again -- cli.py's
# --dialect choices, tui_app.py's dialect picker and autofix.py's
# per-dialect fixer registry all read it, so adding a fourth dialect is
# one dict entry, not a hunt for every place a literal tuple was
# duplicated. "oracle" is deliberately first: it is the default
# everywhere, and several callers present these in order.
DIALECTS: tuple[str, ...] = tuple(_DETECTORS_BY_DIALECT)

_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
_DDL_SUFFIXES = (".sql", ".pks", ".pkb")


def detector_names(dialect: str | None = None) -> tuple[str, ...]:
    """The Finding.detector string each function in _DETECTORS_BY_DIALECT
    actually emits -- derived from each function's own module (every
    detector lives in ora2pg_gap_report/detectors/<name>.py and is named
    after it), not a second, separately-typed-out list. A detector added
    to its dialect's tuple without updating some other hand-maintained
    "list of detector names" is exactly the class of drift this project's
    own registries (gap_registry.py, verification.py's VERIFICATION_MODE)
    already go out of their way to avoid -- this is that same
    single-source-of-truth reasoning applied to the scan loop itself, for
    callers (scripts/doctor.py, tests) that need to know what actually
    runs without calling every detector against fabricated content just
    to read a name back off its own Finding output.

    `dialect=None` (the default) returns every detector registered under
    any dialect -- what scripts/doctor.py's scan-loop-registration-parity
    check needs, since a MySQL detector that exists on disk but was never
    added to _MYSQL_DETECTORS must still be caught, not silently excluded
    just because the check itself doesn't ask for a specific dialect.
    Pass a specific dialect to get only that one's own detectors."""
    detectors = (
        _DETECTORS_BY_DIALECT[dialect]
        if dialect is not None
        else tuple(d for tup in _DETECTORS_BY_DIALECT.values() for d in tup)
    )
    return tuple(detector.__module__.rsplit(".", 1)[-1] for detector in detectors)


@lru_cache(maxsize=1)
def _dialect_by_detector() -> dict[str, str]:
    """{detector name: dialect}, built once from _DETECTORS_BY_DIALECT.

    Still derived from the registry rather than hand-written, so it can't
    drift -- but built once instead of re-derived per lookup.
    dialect_of_detector() used to rebuild every dialect's full name tuple
    (a fresh __module__.rsplit() per detector) on each call, and
    baseline_dialects() calls it once per record in the snapshot: a
    thousand-finding baseline meant a thousand rebuilds of the same
    ~106-entry table. Cached with maxsize=1 because it takes no arguments
    and the registry is fixed at import time."""
    return {
        name: dialect
        for dialect in _DETECTORS_BY_DIALECT
        for name in detector_names(dialect)
    }


def dialect_of_detector(detector: str) -> str | None:
    """Which dialect a detector belongs to -- None if the name isn't a
    detector this build registers at all.

    Derived from _DETECTORS_BY_DIALECT, so it cannot drift the way a
    hand-written {detector: dialect} map would. This is what lets
    --verify work out which dialect a --save snapshot was taken with
    *without* the baseline file having to record it: every detector
    belongs to exactly one dialect, so the detector names already in the
    snapshot determine it. That matters for backward compatibility --
    baselines written before dialects existed at all still verify
    correctly, and their schema_version never had to change (see
    baseline.py's SCHEMA_VERSION and its deliberately narrow
    _REQUIRED_FINDING_FIELDS)."""
    return _dialect_by_detector().get(detector)


def baseline_dialects(baseline: list[dict]) -> tuple[frozenset[str], tuple[str, ...]]:
    """`(dialects the snapshot's detectors belong to, detector names that
    belong to none of them)`, for deciding which dialect --verify should
    re-scan the generated output with.

    Normally the first element holds exactly one dialect: a scan runs one
    dialect's detectors, so a snapshot it wrote can only contain that
    dialect's names. An empty set means an empty snapshot (nothing was
    found pre-migration), and more than one means the file was assembled
    from several scans by hand -- neither is something this module can
    silently pick a dialect for, so both are handed back to the caller to
    report rather than guessed at.

    The second element catches the other realistic drift: a snapshot
    written by a *newer* build that has detectors this one doesn't, or by
    an older one whose detector was since renamed. Those names carry no
    dialect here, and quietly dropping them would let --verify report a
    confident result computed from a subset of the baseline."""
    dialects: set[str] = set()
    unknown: list[str] = []
    for rec in baseline:
        detector = rec["detector"]
        dialect = dialect_of_detector(detector)
        if dialect is None:
            if detector not in unknown:
                unknown.append(detector)
        else:
            dialects.add(dialect)
    return frozenset(dialects), tuple(sorted(unknown))


def _sort_findings(findings: list[Finding]) -> None:
    findings.sort(key=lambda f: (_SEVERITY_ORDER.get(f.severity, 99), f.object_name, f.line))


def scan_source(
    source: str,
    dialect: str = "oracle",
    *,
    errors: list[tuple[str, Exception]] | None = None,
) -> list[Finding]:
    """Run every detector registered for `dialect` against `source`.
    Defaults to "oracle" -- every call site in this codebase before
    MySQL support existed calls this with just `source`, and all of them
    must keep behaving exactly as before with zero code changes on their
    end. See _MYSQL_DETECTORS' own comment for why dialects use separate
    detector tuples rather than one merged list filtered at call time.

    `errors` is opt-in isolation: pass a list and a detector that raises
    is skipped -- its (module name, exception) lands in `errors` instead
    of aborting the scan -- so one broken detector costs only its own
    findings for this source, not every other detector's. Leave it None
    (the default) to keep the original, simpler contract: a detector
    exception propagates immediately, exactly as before this parameter
    existed -- every call site before it did, and TUI scans and this
    module's own tests still rely on that."""
    findings: list[Finding] = []
    for detector in _DETECTORS_BY_DIALECT[dialect]:
        try:
            findings.extend(detector(source))
        except Exception as exc:
            if errors is None:
                raise
            errors.append((detector.__module__.rsplit(".", 1)[-1], exc))
    _sort_findings(findings)
    return findings


def count_objects(source: str) -> int:
    """How many top-level Oracle objects (PACKAGE / PACKAGE BODY, standalone
    PROCEDURE/FUNCTION, TRIGGER, VIEW) this source declares — not lines, not
    findings, just what the file itself declares, via the same masking/
    attribution infrastructure the detectors use. Nested routines inside a
    package aren't counted separately: the package as a whole is the
    migration unit, same as Oracle's own object model.

    Counts every declaration, not distinct names: qualified_name_pattern()
    only captures the final (unqualified) name component, so deduplicating
    by name would silently collapse two genuinely different objects that
    happen to share a bare name in different schemas (hr.emp_pkg vs
    sales.emp_pkg) into one. A file re-declaring the exact same object
    twice (DROP + CREATE under the same name, as in
    docs/research/samples/compound_trigger_dlee.sql) is comparatively rare
    and only affects this display count, not any detector's findings. A
    package whose spec *and* body are both present in the same file counts
    as 2 for the same reason -- both are real, separate 'package' entries
    in enclosing_object_name_index(), and deduplicating them back into one
    logical package would need name-tracking this function deliberately
    doesn't do, for the same low-stakes-display-count reasoning."""
    clean = mask_strings_and_comments(source)
    index = enclosing_object_name_index(clean)
    return sum(
        1 for _, kind, _ in index if kind in ("package", "standalone_routine", "trigger", "view")
    )


def _expand_paths(paths: list[Path]) -> tuple[list[Path], list[Path]]:
    """Expand any directories in `paths` into the .sql/.pks/.pkb files they
    contain (recursively, sorted for deterministic output, extension match
    case-insensitive since exported DDL sometimes carries uppercase
    extensions e.g. from Windows tooling), leaving plain files and
    nonexistent paths untouched -- a nonexistent path still needs to reach
    main()'s existing is_file() check so its "not found" warning keeps
    firing the same way it always has. Returns (files_to_scan,
    directories_with_no_matching_files) so main() can warn about the
    latter -- silently scanning zero files from a directory the user
    pointed at on purpose would be a confusing, warning-free no-op.

    Deduplicates by resolved absolute path, so the same file reached twice
    (e.g. 'schema/ schema/logger.pkb', or two directory arguments that
    overlap) is scanned and reported once, not once per way it was named
    -- otherwise every count (objects_scanned, findings, effort hours)
    would silently double."""
    expanded: list[Path] = []
    empty_dirs: list[Path] = []
    seen: set[Path] = set()

    def _add(candidate: Path) -> None:
        resolved = candidate.resolve()
        if resolved not in seen:
            seen.add(resolved)
            expanded.append(candidate)

    for path in paths:
        if path.is_dir():
            found = sorted(
                p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in _DDL_SUFFIXES
            )
            if not found:
                empty_dirs.append(path)
            for p in found:
                _add(p)
        else:
            _add(path)
    return expanded, empty_dirs


def _connect_by_check(
    path: Path, source: str, ora2pg_bin: str, lang: str = "ru"
) -> tuple[list[Finding], str | None]:
    """Returns (findings, warning) — warning is set instead of raising when
    ora2pg isn't available or fails, since this check is opt-in/best-effort
    by design (see docs/research/step0-show-report-baseline.md section 3:
    low priority for MVP)."""
    if not has_connect_by(source):
        return [], None
    try:
        output = run_estimate_cost(path, guess_object_type(source), ora2pg_bin=ora2pg_bin)
    except Ora2PgNotFoundError:
        return [], i18n.t(lang, "connect_by_not_found", path=path)
    except Ora2PgRunError as exc:
        return [], i18n.t(lang, "connect_by_run_error", path=path, exc=exc)

    # `line` in each risk is a position inside ora2pg's *generated*
    # PostgreSQL output (a tempfile.TemporaryDirectory in run_estimate_cost,
    # already deleted by the time this returns) — it does not correspond to
    # any line in `path`. source_file=path is still correct (that's genuinely
    # the Oracle input that produced this), but stamping ora2pg's internal
    # line number onto it would point the user at an unrelated line in their
    # own file; 0 signals "not a line in this file" instead of a wrong one.
    # object_name/snippet (the enclosing routine and the exact bad LEVEL
    # reference) still identify the problem unambiguously without it.
    return [
        dataclasses.replace(f, source_file=str(path), line=0) for f in find_connect_by_risks(output)
    ], None
