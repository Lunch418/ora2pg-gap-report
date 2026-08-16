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


GAPS: tuple[GapEntry, ...] = (
    GapEntry("001", "autonomous_tx", "autonomous-transaction", ("test_autonomous_tx.py", "test_autonomous_tx_edge_cases.py")),
    GapEntry("002", "merge_delete_clause", "merge-delete-clause", ("test_merge_delete_clause.py",)),
    GapEntry("003", "bulk_collect", "bulk-collect-forall", ("test_bulk_collect.py",)),
    GapEntry("004", "compound_triggers", "compound-trigger", ("test_compound_triggers.py",)),
    GapEntry("005", "connect_by", "connect-by-level", ("test_connect_by.py",)),
    GapEntry("006", "database_link", "database-link", ("test_database_link.py",)),
    GapEntry("007", "model_clause", "model-clause", ("test_model_clause.py",)),
    GapEntry("008", "pivot_clause", "pivot-unpivot", ("test_pivot_clause.py",)),
    GapEntry("009", "object_type", "object-type", ("test_object_type.py",)),
    GapEntry("010", "with_function", "with-function", ("test_with_function.py",)),
    GapEntry("011", "flashback_query", "flashback-query", ("test_flashback_query.py",)),
    GapEntry("012", "global_temp_table", "global-temp-table", ("test_global_temp_table.py",)),
    GapEntry("013", "table_partitioning", "table-partitioning", ("test_table_partitioning.py",)),
    GapEntry("014", "connect_by_nocycle", "connect-by-nocycle", ("test_connect_by_nocycle.py",)),
    GapEntry("015", "context_object", "context", ("test_context_object.py",)),
    GapEntry("016", "insert_all", "insert-all", ("test_insert_all.py",)),
    GapEntry("017", "json_table", "json-table", ("test_json_table.py",)),
    GapEntry("018", "external_table", "external-table", ("test_external_table.py",)),
    GapEntry("019", "sql_macro", "sql-macro", ("test_sql_macro.py",)),
    GapEntry("020", "invisible_column", "invisible-column", ("test_invisible_column.py",)),
    GapEntry("021", "collection_type", "collection-type", ("test_collection_type.py",)),
    GapEntry("022", "cross_apply", "cross-apply", ("test_cross_apply.py",)),
    GapEntry("023", "oracle_text", "oracle-text", ("test_oracle_text.py",)),
    GapEntry("024", "recursive_with", "recursive-with", ("test_recursive_with.py",)),
    GapEntry("025", "invisible_index", "invisible-index", ("test_invisible_index.py",)),
    GapEntry("026", "read_only_table", "read-only-table", ("test_read_only_table.py",)),
    GapEntry("027", "materialized_view_log", "materialized-view-log", ("test_materialized_view_log.py",)),
    GapEntry("028", "identity_column", "identity-column", ("test_identity_column.py",)),
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
