*English | [Русский](ROADMAP.ru.md)*

# Roadmap

This document captures the project's full vision — where it could grow if
it becomes a genuinely needed tool rather than a weekend project. There
are no deadlines: the items below aren't a quarterly plan, they're a
backlog, and items only get pulled out of it once there's a confirmed
reason (a real user, a real issue, real pain). See the rule at the end of
the document.

Status current as of v0.6.0 (2026-08-18).

## How to read this list

Three sections:

- **Already there** — things many people would expect to see here as a
  "future feature," but that's already implemented, just not always
  obvious from the README.
- **Near-term** — small, cheap steps that round out capabilities that
  already exist, or close a real, already-visible gap.
- **Backlog** — larger directions. Not sorted by priority, and not a
  promise. Each is waiting for its own trigger: a specific user, a
  specific issue, a specific case the current tool doesn't cover.

## Already there

The core "evidence-based verification layer" — the whole reason this
project exists — is already in place:

- **Verification, not guessing**: `--verify` compares the converted
  PostgreSQL code against a pre-migration snapshot (`--baseline`) at
  detector granularity and gives `STILL_PRESENT` / `NOT_DETECTED` /
  `NOT_VERIFIABLE` — `NOT_VERIFIABLE` is first-class, not hidden or
  passed off as "fixed".
- **Baseline / diff**: `--save` + `--baseline` — `NEW` / `RESOLVED` /
  `UNCHANGED` between runs.
- **CI gate**: `--fail-on high|medium|low` — exit code 1 if there's a
  finding at that severity or above, independent of the `--severity`/
  `--object` output filters.
- **Native GitHub/GitLab code scanning integration**: `--format sarif` —
  SARIF 2.1.0. Via `github/codeql-action/upload-sarif`, GitHub draws the
  findings inline in the PR itself, no custom bot or Action needed for
  that (see "Near-term" — only a documented example is missing).
- **Evidence pages**: `--explain GAP-NNN` + `docs/research/gap-*.md` (47
  of them) — minimal example, real `ora2pg` output, what happens in
  PostgreSQL, the severity rationale.
- **Reproduce for CONNECT BY**: `--check-connect-by` actually runs an
  installed `ora2pg` and checks the generated `WITH RECURSIVE` against a
  specific, known `LEVEL` bug — not a hypothesis, a reproduced fact.
- **HTML/JSON/CSV/Markdown reports**: `--format html` — a self-contained
  page with no external resources, for showing a non-engineer.
- **Registry guardian**: `scripts/doctor.py` — catches drift between the
  detector code, `gap_registry.py`, `verification.py`, the research docs,
  and the tests. Part of CI.
- **i18n**: RU/EN at the UI and finding-text level (`--lang`,
  `--set-lang`), README and README.ru.md.
- **Offline install**: `scripts/build_offline_bundle.py` + automatic
  bundle build in CI on every release (for closed-network environments,
  a common case for Oracle→PostgreSQL migrations).
- **CI recipe**: [`docs/ci-integration.md`](docs/ci-integration.md) — a
  pipeline alongside `ora2pg` (a gate before conversion, `--check-
  connect-by`, `--verify` after) and a sample GitHub Actions workflow
  that, via `--format sarif` + `upload-sarif`, gets findings inline in the
  PR with no custom bot or Action.
- **Verification capability matrix**:
  [`docs/verification-capability-matrix.md`](docs/verification-capability-matrix.md)
  — for each of the 47 gaps, explicitly which verification mode it has
  (`verbatim`/`not_verifiable`/`generated_only`) and why, cross-checked
  against `VERIFICATION_MODE` in the code line by line (not written by
  eye).
- **`failure_stage`**: at which stage a gap actually becomes visible —
  `deployment`/`runtime`/`semantic` (`conversion` is defined but has never
  been needed, see `docs/failure-stage-notes.md`). Rolled out to all 47
  gaps (except two deliberate exceptions — findings that aren't about the
  shape of the code but about `--estimate_cost` underestimating effort),
  `doctor.py` requires full coverage. Shown not just in `--explain`, but
  in the main report too: columns in `--format markdown`/`html`, fields in
  `--format json`/`csv`, a `properties` entry on the rule in SARIF, a
  "GAP-NNN · stage" line in the terminal output's explanation panel,
  fields in `--save` snapshots. `schemas/report.schema.json`/`schemas/
  baseline.schema.json` updated to match.
- **`--tui`**: an interactive screen built on `textual` (an optional
  `[tui]` extra, not part of the base install) — pick a path with mouse/
  keyboard instead of flags, scan with a button, click a finding to open
  its full explanation with `GAP-NNN`/`failure_stage`. The first version
  is deliberately narrow: scanning and browsing only, no `--save`/
  `--baseline`/`--verify`/`--check-connect-by` from inside it, and no
  multi-path selection, see the backlog below for expanding it.

## Near-term

Small, cheap steps that round out what already exists:

- The explain/evidence docs (`docs/research/gap-*.md`) were written for
  contributors, not the end user — worth checking how readable they are
  without codebase context.

## Backlog (no order, no deadlines)

The ideas below are at varying degrees of maturity — from "almost ready to
pull out" to "needs a real case to know if it's even worth doing." Each is
waiting for its trigger.

### Understanding risk
- A separate "silent loss" category — in practice already covered as part
  of `failure_stage`: the `semantic` value is exactly this (there will
  never be an error, the behavior is just silently different). A separate
  taxonomy on top of `failure_stage` isn't needed for now.

### Interactive mode
- `--tui`: multi-path selection currently works only through the tree
  ("Add to selection" one at a time) — drag-select/checkboxes in the tree
  itself aren't implemented, in case real usage calls for it.

### Migration workflow
- `waiver`/suppression with an explicit expiry — an accepted and
  documented risk, not a forgotten one.
- A migration checklist generated from a specific run's findings.
- Migration recipes: `docs/recipes/` — for each class of problem (not
  each detector) a separate "problem → migration pattern → alternatives"
  document, distinct from the detectors' own evidence docs.

### Ecosystem
- An official GitHub Action example (a wrapper around the CLI + SARIF,
  not a separate service).
- `--annotate`: safely inserting comments directly into the converted SQL
  file next to findings (`-- ora2pg-gap-report: GAP-023, see ...`) —
  doesn't rewrite anything, doesn't change the file's validity, just puts
  context where the developer is going to open the file anyway.

### Trust and transparency
- A version compatibility matrix: which `ora2pg` versions each behavior
  was actually verified against.
- Public metrics with no false precision: for example "every registered
  GAP has a regression fixture" — but only for as long as that claim is
  actually true (checked by `doctor.py`).

## Prioritization rule

**No feature gets picked up without a real reason.** A real reason is a
specific issue, a specific user, a specific reproducible case the tool
doesn't cover today. Not "that would be cool," not "because the big
enterprise tools do it."

Same principle already in force for the detectors themselves
(`CONTRIBUTING.md`): a finding doesn't make it into the registry until
it's confirmed in practice. The roadmap works the same way — an item
doesn't go into development until there's practical confirmation for it.
