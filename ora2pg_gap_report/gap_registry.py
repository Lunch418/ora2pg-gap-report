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
    GapEntry("001", "autonomous_tx", "autonomous-transaction", ("test_autonomous_tx.py", "test_autonomous_tx_edge_cases.py"), severity="high"),
    GapEntry("002", "merge_delete_clause", "merge-delete-clause", ("test_merge_delete_clause.py",), severity="high", failure_stage="runtime"),
    GapEntry("003", "bulk_collect", "bulk-collect-forall", ("test_bulk_collect.py",), severity="high", failure_stage="runtime"),
    GapEntry(
        "004", "compound_triggers", "compound-trigger", ("test_compound_triggers.py",), severity="high", failure_stage="semantic"
    ),
    GapEntry("005", "connect_by", "connect-by-level", ("test_connect_by.py",), severity="high", failure_stage="runtime"),
    GapEntry("006", "database_link", "database-link", ("test_database_link.py",), severity="high", failure_stage="runtime"),
    GapEntry("007", "model_clause", "model-clause", ("test_model_clause.py",), severity="high", failure_stage="runtime"),
    GapEntry("008", "pivot_clause", "pivot-unpivot", ("test_pivot_clause.py",), severity="high", failure_stage="runtime"),
    # object_type: failure_stage left unset for the same class of reason
    # as autonomous_tx -- its finding is that --estimate_cost/SHOW_REPORT
    # returns *no* number at all for TYPE objects (not a broken/silent
    # runtime behavior), see docs/research/gap-009-object-type.md.
    GapEntry("009", "object_type", "object-type", ("test_object_type.py",), severity="high"),
    GapEntry("010", "with_function", "with-function", ("test_with_function.py",), severity="high", failure_stage="runtime"),
    GapEntry("011", "flashback_query", "flashback-query", ("test_flashback_query.py",), severity="high", failure_stage="runtime"),
    GapEntry("012", "global_temp_table", "global-temp-table", ("test_global_temp_table.py",), severity="high", failure_stage="semantic"),
    GapEntry("013", "table_partitioning", "table-partitioning", ("test_table_partitioning.py",), severity="high", failure_stage="semantic"),
    GapEntry("014", "connect_by_nocycle", "connect-by-nocycle", ("test_connect_by_nocycle.py",), severity="high", failure_stage="deployment"),
    GapEntry("015", "context_object", "context", ("test_context_object.py",), severity="medium", failure_stage="semantic"),
    GapEntry("016", "insert_all", "insert-all", ("test_insert_all.py",), severity="high", failure_stage="runtime"),
    GapEntry("017", "json_table", "json-table", ("test_json_table.py",), severity="high", failure_stage="runtime"),
    GapEntry("018", "external_table", "external-table", ("test_external_table.py",), severity="high", failure_stage="semantic"),
    GapEntry("019", "sql_macro", "sql-macro", ("test_sql_macro.py",), severity="high", failure_stage="runtime"),
    GapEntry("020", "invisible_column", "invisible-column", ("test_invisible_column.py",), severity="high", failure_stage="semantic"),
    GapEntry(
        "021", "collection_type", "collection-type", ("test_collection_type.py",), severity="high", failure_stage="deployment"
    ),
    GapEntry("022", "cross_apply", "cross-apply", ("test_cross_apply.py",), severity="high", failure_stage="runtime"),
    GapEntry("023", "oracle_text", "oracle-text", ("test_oracle_text.py",), severity="high", failure_stage="runtime"),
    GapEntry("024", "recursive_with", "recursive-with", ("test_recursive_with.py",), severity="high", failure_stage="runtime"),
    GapEntry("025", "invisible_index", "invisible-index", ("test_invisible_index.py",), severity="medium", failure_stage="semantic"),
    GapEntry(
        "026", "read_only_table", "read-only-table", ("test_read_only_table.py",), severity="high", failure_stage="semantic"
    ),
    GapEntry("027", "materialized_view_log", "materialized-view-log", ("test_materialized_view_log.py",), severity="high", failure_stage="semantic"),
    GapEntry(
        "028", "identity_column", "identity-column", ("test_identity_column.py",), severity="high", failure_stage="deployment"
    ),
    GapEntry("029", "rowid_type", "rowid-urowid", ("test_rowid_type.py",), severity="high", failure_stage="runtime"),
    GapEntry("030", "sequence_cycle", "sequence-cycle", ("test_sequence_cycle.py",), severity="high", failure_stage="runtime"),
    GapEntry(
        "031", "default_on_null", "default-on-null", ("test_default_on_null.py",), severity="high", failure_stage="deployment"
    ),
    GapEntry("032", "public_synonym", "public-synonym", ("test_public_synonym.py",), severity="high", failure_stage="deployment"),
    GapEntry(
        "033", "virtual_column", "virtual-column", ("test_virtual_column.py",), severity="medium", failure_stage="semantic"
    ),
    GapEntry("034", "nested_subprogram", "nested-subprogram", ("test_nested_subprogram.py",), severity="high", failure_stage="runtime"),
    GapEntry(
        "035",
        "conditional_compilation",
        "conditional-compilation",
        ("test_conditional_compilation.py",),
        severity="high", failure_stage="runtime",
    ),
    GapEntry("036", "package_state", "package-state", ("test_package_state.py",), severity="high", failure_stage="runtime"),
    GapEntry(
        "037",
        "index_organized_table",
        "index-organized-table",
        ("test_index_organized_table.py",),
        severity="medium", failure_stage="semantic",
    ),
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
