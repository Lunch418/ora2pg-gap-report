# failure_stage: rollout notes

This is not the feature's public documentation (the part a user needs is
`--explain`'s "Fails at" line and `gap_registry.py`'s own docstring for
the field). These are internal notes on the decision recorded in
`ROADMAP.md`: "start small, on 5-10 gaps; if the model fits, roll it out
to all of them". What follows is what was checked on the trial run, what
held up during the full rollout, and what surprises the rollout turned
up.

**Status: rollout complete.** Every gap is classified except two
deliberate exemptions (`FAILURE_STAGE_EXEMPT_DETECTORS`). `doctor.py` now
requires full coverage — a new gap with no decision on `failure_stage`
will not pass the check.

## Final distribution (105 gaps)

| Stage | Count |
|---|---|
| `deployment` | 30 |
| `runtime` | 46 |
| `semantic` | 26 |
| `conversion` | 1 |
| no stage (`FAILURE_STAGE_EXEMPT_DETECTORS`) | 2 |

These counts cover all 105 gaps, the MySQL (GAP-068..086) and MSSQL
(GAP-087..105) batches included; the analysis in the sections below was
written when the registry held 67 Oracle gaps, and its conclusions have
not been re-examined against the two later batches. The per-gap list is in
`--explain GAP-NNN` (the "Fails at" line) and in
`ora2pg_gap_report/gap_registry.py` itself.

## Methodology

As on the trial run: the value was taken only from the "Observed problem"
section of the gap's own research document — nothing was invented. Where
a document does not name the moment of failure explicitly, the gap was
left with no stage rather than with a guessed value.

## What held up from the trial run

1. **`conversion` was not needed for the first 47 — and was needed for
   the 48th.** The trial run's conclusion ("a DEBUG line in `ora2pg`'s log
   does not coincide with the real moment of failure — it is either
   `deployment` or `semantic`") held right up to GAP-059
   (`authid_clause`), the first and so far only gap with this stage. And
   what makes it telling is exactly how it differs from every earlier
   candidate for `conversion`: there, one wanted to assign the stage from
   a DEBUG line in the log, whereas here **there is no log line at all**.
   A procedure with `AUTHID` simply never reaches the output — no error,
   no warning, no `unhandled line`. There is nothing to break at
   `deployment` or `runtime`: the object is not in the target database.

   So the `conversion` stage, which twice in a row looked like a dead
   category worth removing, turned out to be needed not for "visible in
   the log" but for precisely the opposite case — "visible nowhere". A
   good illustration of why a taxonomy keeps a category that nothing has
   matched yet.
2. **`compile` as a separate stage is still unnecessary** — not one gap
   has called for it, the GAP-048..067 batch included;
   `check_function_bodies = false` in ora2pg's dump (mentioned explicitly
   in at least 10 of the 67 research documents that existed then, and in
   60 of the 105 today — `grep -rl check_function_bodies
   docs/research/gap-*.md`) reliably defers a
   function body's syntax errors to the first call — everywhere except the
   one explicit exception below.

## Two new discoveries from the full rollout

Which are, in fact, why it was worth rolling out one gap at a time rather
than in a single eyeballed commit:

1. **GAP-014 (`connect_by_nocycle`) — the only exception to "CREATE
   PROCEDURE is always runtime".** Its own research document states
   plainly that `CREATE PROCEDURE` fails at load time already, "not only
   on the first call — that is, even earlier than for the typical gaps ...
   where `check_function_bodies = false` normally defers the error". The
   cause is not the syntax of the finding itself but that the conversion
   structurally breaks the whole block (the generated `WITH RECURSIVE`
   lands before `DECLARE`, and the `DECLARE`/`CURSOR` nesting is
   violated) — badly enough for PostgreSQL's parser to stumble before
   `check_function_bodies` would ever get the chance to defer the check.
   Classified as `deployment`, not `runtime` — the stage's definition in
   `gap_registry.py` now spells this exception out.
2. **GAP-009 (`object_type`) — the second exemption from the taxonomy
   altogether, not just `autonomous_tx`.** The finding is not about the
   shape of the code but about `--estimate_cost`/`SHOW_REPORT` returning
   no number whatsoever for `TYPE` objects (not an understated estimate —
   a complete absence). The same class as `autonomous_tx`, so it was moved
   into the shared `FAILURE_STAGE_EXEMPT_DETECTORS` rather than left as
   "not classified yet".
3. **GAP-032 (`public_synonym`) — a mixed case, classified by the more
   frequent and earlier scenario.** When the synonym's name matches the
   target table's name (per the document, "the most common case in
   reality"), the `CREATE VIEW` fails immediately — `deployment`. When the
   names differ, there is no error at that stage at all: the view quietly
   binds to whatever `search_path` resolves at execution time, which is
   closer to `semantic`. `deployment` was chosen as the primary value and
   documented as the more frequent and earlier-detected scenario — but
   this is the one gap in the registry where a single value really does
   flatten two different real outcomes.

## The public report (JSON/HTML/SARIF) now carries this field too

The decision from the previous version of this document ("the schema
extension is deferred until coverage is complete") has been carried out:
now that every gap is classified, `gap_number`/`failure_stage` have been
added to every format, not just `--explain`:

- **`--format json`/`csv`**: two new fields/columns per finding, computed
  through `gap_registry.gap_metadata(detector)` at serialization time (not
  stored on the `Finding` itself — the same approach already used for
  `DetectorVerification` in `verification.py`).
- **`--format markdown`/`html`**: two new table columns, "GAP" and "Fails
  at"/"Когда ломается".
- **`--format sarif`**: `properties.gapNumber`/`properties.failureStage`
  on each rule (a SARIF-compatible arbitrary bag — not part of the formal
  specification, but the same place `helpUri` already lived).
- **Terminal output**: the "Explanations" panel gained a third line —
  `GAP-NNN · <short stage>`, in a dim style, below the explanation text.
- **`--save` snapshots**: these now carry both fields too
  (`baseline.py`'s `save_baseline()`) — `load_baseline()` still requires
  only `group_key`/`schema_version`, so older snapshots without these
  fields keep loading without error, and nothing reads them for
  `--baseline`/`--verify` matching.

`schemas/report.schema.json` and `schemas/baseline.schema.json` were
updated identically for the shared fields (checked by
`tests/test_report_and_baseline_schemas_share_identical_finding_field_definitions`).
`gap_number` is `null` for a detector with no registered gap (for example
`dbms_utl_calls`); `failure_stage` is additionally `null` for the two gaps
in `FAILURE_STAGE_EXEMPT_DETECTORS`.
