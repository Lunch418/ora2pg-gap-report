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
