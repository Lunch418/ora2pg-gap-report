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
from .detectors.multiset_operator import find_multiset_operators
from .detectors.nested_subprogram import find_nested_subprograms
from .detectors.object_table import find_object_tables
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

_DETECTORS = (
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
)
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
_DDL_SUFFIXES = (".sql", ".pks", ".pkb")


def detector_names() -> tuple[str, ...]:
    """The Finding.detector string each function in _DETECTORS actually
    emits -- derived from each function's own module (every detector
    lives in ora2pg_gap_report/detectors/<name>.py and is named after
    it), not a second, separately-typed-out list. A detector added to
    _DETECTORS without updating some other hand-maintained "list of
    detector names" is exactly the class of drift this project's own
    registries (gap_registry.py, verification.py's VERIFICATION_MODE)
    already go out of their way to avoid -- this is that same
    single-source-of-truth reasoning applied to the scan loop itself, for
    callers (scripts/doctor.py, tests) that need to know what actually
    runs without calling every detector against fabricated content just
    to read a name back off its own Finding output."""
    return tuple(detector.__module__.rsplit(".", 1)[-1] for detector in _DETECTORS)


def _sort_findings(findings: list[Finding]) -> None:
    findings.sort(key=lambda f: (_SEVERITY_ORDER.get(f.severity, 99), f.object_name, f.line))


def scan_source(source: str) -> list[Finding]:
    findings: list[Finding] = []
    for detector in _DETECTORS:
        findings.extend(detector(source))
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
