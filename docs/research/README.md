# Research

Validation material for the project's premises, plus the registry of
confirmed gaps — the empirical base the detectors are built on (for the
methodology, see the "Methodology" section of the project's main README).

- `GAP_REGISTRY.md` — the registry of every confirmed gap with its
  number (GAP-NNN), status and the `ora2pg` version it was confirmed on.
  Start here.
- `AUDIT.md` — a consolidated check of the evidence behind each of the
  21 gaps it covers: research document, real ora2pg output,
  expected/actual, detector, regression tests (including guard tests
  against false positives), and verification on a large open-source
  corpus where applicable.
- `gap-001-autonomous-transaction.md` … `gap-105-mssql-rowversion.md` —
  the detailed research for each gap: minimal example, ora2pg output,
  observed problem, verdict.
- `rejected-hypotheses.md` — hypotheses that were tested and not
  confirmed (other than those rejected in
  `step0-show-report-baseline.md`) — ora2pg actually handles them
  correctly and no detector is needed.
- `step0-show-report-baseline.md` — the original survey of what `ora2pg
  SHOW_REPORT` already shows out of the box for the five classes of
  construct assumed at the start. It contains rejected hypotheses too
  (`CREATE PACKAGE`, for instance, is not a gap), not only confirmed
  ones; the confirmed ones from that document were later moved into
  separate `gap-NNN-*.md` files for consistency with the findings added
  afterwards.

Every document here has a Russian counterpart at the same name with a
`.ru.md` suffix.
