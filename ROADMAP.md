*English | [Русский](ROADMAP.ru.md)*

# Roadmap

This document captures the project's full vision - where it could grow if
it becomes a genuinely needed tool rather than a weekend project. There
are no deadlines: the items below aren't a quarterly plan, they're a
backlog, and items only get pulled out of it once there's a confirmed
reason (a real user, a real issue, real pain). See the rule at the end of
the document.

Status current as of v0.14.0 (2026-10-08).

## How to read this list

Three sections:

- **Already there** - things many people would expect to see here as a
  "future feature," but that's already implemented, just not always
  obvious from the README.
- **Near-term** - small, cheap steps that round out capabilities that
  already exist, or close a real, already-visible gap.
- **Backlog** - larger directions. Not sorted by priority, and not a
  promise. Each is waiting for its own trigger: a specific user, a
  specific issue, a specific case the current tool doesn't cover.

## Already there

The core "evidence-based verification layer" - the whole reason this
project exists - is already in place:

- **126 confirmed gaps across three source dialects**: 80 Oracle, 25
  MySQL/MariaDB (`--dialect mysql`, as for `ora2pg -m`) and 21 SQL Server
  (`--dialect mssql`, as for `ora2pg -M`), plus the `dbms_utl_calls`
  classifier. Each one reproduced on a real `ora2pg` 25.0 + PostgreSQL 16
  run before it was added.
- **Load check against a real PostgreSQL**: `--load-check
  docker|DSN` loads `ora2pg`'s generated files into a real server (a
  throwaway container by default) in one transaction that is rolled back,
  with `check_function_bodies` forced on, and ties every statement that
  fails to a GAP-NNN, to `--fix`, or to an earlier failure. Errors the
  registry doesn't know are listed apart - exactly the material new gaps
  come from.
- **Migration recipes**: fifteen pages in `docs/recipes/`, one
  per class of problem, each with the PostgreSQL pattern and what does not
  carry over. Their SQL runs in the test suite against a real PostgreSQL
  16, `ASSERT`s included, in both languages. Every report links each gap
  to its recipe.
- **A checklist that remembers**: `-f checklist -o
  MIGRATION.md` writes the work as a Markdown task list; regenerating it
  keeps the ticks and ticks what the source no longer contains.
- **One-command migration**: `--migrate OUT_DIR` runs scan,
  prepare, ora2pg, fix and load in order, into one directory - and puts
  back what only the source still knows (statement triggers, package
  constants, MySQL ENUM types). Also from the TUI's Migrate screen.
- **Docker image and GitHub Action**: `ghcr.io/lunch418/ora2pg-gap-report`
  carries the tool, ora2pg and psql; the repository is an Action that
  scans, uploads SARIF to code scanning and gates a pull request.
- **Source preparation**: `--prepare` rewrites what ora2pg's
  parser trips over in the dump itself, before ora2pg runs, for eight gaps
  that cannot be repaired in its output afterwards.
- **Autofix**: `--fix`/`--write` - seven mechanical fixes for `ora2pg`'s
  generated code (GAP-024, GAP-028 and GAP-123 for Oracle, GAP-075 for
  MySQL, GAP-091, GAP-100 and GAP-125 for T-SQL), dry
  run by default, preserving the file's encoding, line endings and BOM.

- **Verification, not guessing**: `--verify` compares the converted
  PostgreSQL code against a pre-migration snapshot (`--baseline`) at
  detector granularity and gives `STILL_PRESENT` / `NOT_DETECTED` /
  `NOT_VERIFIABLE` - `NOT_VERIFIABLE` is first-class, not hidden or
  passed off as "fixed".
- **Baseline / diff**: `--save` + `--baseline` - `NEW` / `RESOLVED` /
  `UNCHANGED` between runs.
- **CI gate**: `--fail-on high|medium|low` - exit code 1 if there's a
  finding at that severity or above, independent of the `--severity`/
  `--object` output filters.
- **Native GitHub/GitLab code scanning integration**: `--format sarif` -
  SARIF 2.1.0. Via `github/codeql-action/upload-sarif`, GitHub draws the
  findings inline in the PR itself, no custom bot or Action needed for
  that (see "Near-term" - only a documented example is missing).
- **Evidence pages**: `--explain GAP-NNN` + `docs/research/gap-*.md` (126
  of them, each in English and Russian) - minimal example, real `ora2pg`
  output, what happens in PostgreSQL, the severity rationale.
- **Reproduce for CONNECT BY**: `--check-connect-by` actually runs an
  installed `ora2pg` and checks the generated `WITH RECURSIVE` against a
  specific, known `LEVEL` bug - not a hypothesis, a reproduced fact.
- **HTML/JSON/CSV/Markdown reports**: `--format html` - a self-contained
  page with no external resources, for showing a non-engineer: the failure
  stages first, each gap once, filters without JavaScript, a dark theme.
- **Registry guardian**: `scripts/doctor.py` - catches drift between the
  detector code, `gap_registry.py`, `verification.py`, the research docs,
  and the tests. Part of CI.
- **i18n**: RU/EN at the UI and finding-text level (`--lang`,
  `--set-lang`), README and README.ru.md.
- **Offline install**: `scripts/build_offline_bundle.py` + automatic
  bundle build in CI on every release (for closed-network environments,
  a common case for Oracle->PostgreSQL migrations).
- **CI recipe**: [`docs/ci-integration.md`](docs/ci-integration.md) - a
  pipeline alongside `ora2pg` (a gate before conversion, `--check-
  connect-by`, `--verify`, `--fix` and `--load-check` after) and a sample
  GitHub Actions workflow
  that, via `--format sarif` + `upload-sarif`, gets findings inline in the
  PR with no custom bot or Action.
- **Verification capability matrix**:
  [`docs/verification-capability-matrix.md`](docs/verification-capability-matrix.md)
  - for each of the 126 gaps, explicitly which verification mode it has
  (`verbatim`/`not_verifiable`/`generated_only`) and why, cross-checked
  against `VERIFICATION_MODE` in the code line by line (not written by
  eye).
- **`failure_stage`**: at which stage a gap actually becomes visible -
  `deployment`/`runtime`/`semantic` (`conversion` is defined but has never
  been needed, see `docs/failure-stage-notes.md`). Rolled out to all 126
  gaps (except two deliberate exceptions - findings that aren't about the
  shape of the code but about `--estimate_cost` underestimating effort),
  `doctor.py` requires full coverage. Shown not just in `--explain`, but
  in the main report too: columns in `--format markdown`/`html`, fields in
  `--format json`/`csv`, a `properties` entry on the rule in SARIF, a
  "GAP-NNN · stage" line in the terminal output's explanation panel,
  fields in `--save` snapshots. `schemas/report.schema.json`/`schemas/
  baseline.schema.json` updated to match.
- **`--tui`**: an interactive screen built on `textual` (an optional
  `[tui]` extra, not part of the base install) - pick paths with mouse/
  keyboard instead of flags ("Add to selection" for several), scan with a
  button, compare against a baseline, run `--verify` and the CONNECT BY
  check, save a baseline, and browse the results with the explanation
  following the cursor.
- **Version stamps**: every gap records the `ora2pg` and PostgreSQL
  versions it was confirmed on and when (`gap_registry.py`,
  `GAP_REGISTRY.md`, shown by `--explain`); a run that calls a different
  installed `ora2pg` says so.
- **A regression test per gap**: `doctor.py` fails the build unless every
  registered gap has a research doc, a detector, a positive and a guard
  test, both translations and a verification mode.

## Near-term

Small, cheap steps that round out what already exists:

- **More `--fix` candidates**: go through the gaps `--load-check` reports
  as failing at load time and pick out the ones whose fix is as
  unambiguous as GAP-028's. Each one confirmed on the test bench first.
- **`--annotate`**: comments next to each finding in the converted SQL
  (`-- ora2pg-gap-report: GAP-023, see ...`) - rewrites nothing, puts the
  context where the developer opens the file anyway.
- The explain/evidence docs (`docs/research/gap-*.md`) were written for
  contributors, not the end user - worth checking how readable they are
  without codebase context.

## Backlog (no order, no deadlines)

The ideas below are at varying degrees of maturity - from "almost ready to
pull out" to "needs a real case to know if it's even worth doing." Each is
waiting for its trigger.

### Understanding risk
- A separate "silent loss" category - in practice already covered as part
  of `failure_stage`: the `semantic` value is exactly this (there will
  never be an error, the behavior is just silently different). A separate
  taxonomy on top of `failure_stage` isn't needed for now.

### Interactive mode
- `--tui`: multi-path selection currently works only through the tree
  ("Add to selection" one at a time) - drag-select/checkboxes in the tree
  itself aren't implemented, in case real usage calls for it.

### Migration workflow
- `waiver`/suppression with an explicit expiry - an accepted and
  documented risk, not a forgotten one.
- `--load-check` on its own from inside `--tui` (today it runs there only
  as part of Migrate).
- More recipes, for the gap classes that have none yet (object types,
  `MODEL`, `MATCH_RECOGNIZE`, compound triggers, Oracle Text, `ROWNUM` in
  DML). Each one needs code that passes the recipe test, the same bar as
  the fifteen there now.

### Trust and transparency
- Re-verifying the registry against newer `ora2pg` releases and
  PostgreSQL 17/18, so the version stamps say more than one pair.
  `--load-check docker:postgres:17` already makes the PostgreSQL half
  cheap to try.

## Prioritization rule

**No feature gets picked up without a real reason.** A real reason is a
specific issue, a specific user, a specific reproducible case the tool
doesn't cover today. Not "that would be cool," not "because the big
enterprise tools do it."

Same principle already in force for the detectors themselves
(`CONTRIBUTING.md`): a finding doesn't make it into the registry until
it's confirmed in practice. The roadmap works the same way - an item
doesn't go into development until there's practical confirmation for it.
