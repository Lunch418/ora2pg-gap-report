*English | [Русский](CHANGELOG.ru.md)*

# Changelog

Format loosely based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
The project follows [SemVer](https://semver.org/) in a simplified form
until it reaches 1.0.0: minor version bumps for new detectors/features,
patch for fixes to existing ones.

## [Unreleased]

### Added
- `--fix` (+ `--write`): applies the one known mechanical, provably
  safe correction we currently trust to `--fix` — GAP-028's identity-column
  double-paren bug in ora2pg's *generated* PostgreSQL output (`GENERATED
  ... AS IDENTITY ((...))` → `IDENTITY (...)`, see `autofix.py`'s module
  docstring for why this gap specifically qualifies and most others don't).
  Dry-run by default (prints a unified diff, touches nothing on disk);
  `--write` is required to actually rewrite the files. Standalone mode,
  same as `--verify`/`--tui`/`--explain` — not combinable with the
  scan-shaping flags.
- English versions of `CODE_OF_CONDUCT.md`/`CONTRIBUTING.md`/`SECURITY.md`
  (the canonical filenames now, matching `README.md`), with the previous
  Russian text moved to `*.ru.md` and a language switcher on both, same
  split as `README.md`/`README.ru.md`.
- Same treatment for `ROADMAP.md`/`docs/DEVELOPMENT.md`/
  `docs/ARCHITECTURE.md`. `scripts/doctor.py`'s detector-file-tree parity
  check reads `docs/ARCHITECTURE.md` by path, so it now checks the
  English version; it only parses the tree's `.py` filenames, not the
  comment text, so translating the inline comments didn't need any
  change to the check itself (verified: `doctor.py` still passes clean).
- English versions of `docs/ci-integration.md`/`docs/verification-
  capability-matrix.md`, same split as every other doc so far.
- `pyproject.toml`'s `[project.urls]` gained `Homepage`, `Documentation`,
  `Changelog`, and `Issues` -- it only had `Repository` before, so PyPI's
  project page was missing the links it can otherwise auto-render.

### Changed
- License switched from MIT to Apache-2.0 (`LICENSE`, `pyproject.toml`,
  both READMEs). MIT already required keeping the copyright/license notice
  on redistribution; Apache-2.0 additionally requires modified files to
  carry a notice that they were changed. Sole author, no other
  contributors to get consent from.
- New `core.py`: `scan_source()`/`count_objects()`/`_expand_paths()`/
  `_connect_by_check()`/`_sort_findings()` (plus `_DETECTORS`/
  `detector_names()`) moved there from `cli.py`. `tui_app.py` used to
  import all five straight from `cli.py` — the interactive mode was
  coupled to the flag-based CLI's own internals instead of to a shared
  neutral layer both are peers of. `cli.py` re-exports the same names, so
  `main()` and external imports (`from ora2pg_gap_report.cli import
  scan_source`, etc.) don't change.

### Fixed
- `cli.py` gains `detector_names()` — each detector's `Finding.detector`
  string derived from its function's own `__module__`, not a second,
  hand-typed list. `tests/test_terminal_report.py`'s remediation-hint
  coverage test used to hardcode its own "known detector set" instead;
  that set had drifted 9 detectors behind `cli._DETECTORS` by the time
  this was caught (GAP-029..037 were all missing from it) — it was
  silently checking only a stale subset the whole time, not real
  completeness. `scripts/doctor.py` also gains a check using the same
  function: every detector module on disk (other than `connect_by`,
  deliberately opt-in via `--check-connect-by`) must actually be
  registered in `cli._DETECTORS` — previously nothing verified this, so
  a detector fully wired into every other registry but never added to
  the scan loop itself would have shipped silently dead (registered,
  tested, documented, and never actually run).

### Performance
- `mask_strings_and_comments()`/`mask_dynamic_sql_visible()`/
  `enclosing_object_name_index()` (`plsql_lex.py`) are now cached
  (`functools.lru_cache`) — ~37 detectors each called
  `mask_strings_and_comments()` with the exact same `source` while
  scanning one file (a third of them also call
  `mask_dynamic_sql_visible()`/`enclosing_object_name_index()`),
  recomputing the same O(n) pass over the file 20-70 times over. On
  `docs/research/samples/logger.pkb` (80KB): `scan_source()` went from
  ~0.94s to ~0.09s on a cold cache (~10x), and the full local test suite
  dropped from ~60s to ~22s. `enclosing_object_name_index()` also now
  returns a `tuple` instead of a `list` — with a shared cached value, an
  accidental in-place mutation in one caller can no longer silently
  corrupt what every other caller sees.

### Added
- `mypy` in CI (the `lint` job, config in `pyproject.toml`) with
  `disallow_untyped_defs` — not just "doesn't fail on already-annotated
  code," it actually requires an annotation on every function in
  `ora2pg_gap_report/` and `scripts/`. `oracledb` (the optional `oracle`
  extra) is marked `ignore_missing_imports` — its types are only used
  under `if TYPE_CHECKING:`, so the package stays importable without it.
- `--lang`/`--set-lang`/`--tui` now also cover `--help`'s own text (the
  command description and each flag's `help=`) and all of `--tui`'s UI
  chrome (buttons, status/error text, table headers), not just findings
  and reports like before. `--help` resolves the language from the raw
  argv before full parsing even happens (`cli.py`'s
  `_peek_lang_for_help()`) — this used to be explicitly documented as
  unsolved in `i18n.py`'s module docstring.

### Security
- `--format csv`: a field starting with `=`, `+`, `-`, `@`, a tab, or CR
  (taken straight from the scanned Oracle code — `snippet`/`object_name`/
  `source_file`) now gets escaped with a leading `'` — prevents formula
  execution when the report is opened in Excel/Sheets/LibreOffice
  (formula injection).
- `--format sarif`: `artifactLocation.uri` no longer takes the raw file
  path as-is — it's now a valid URI reference (RFC 3986, via
  `urllib.parse.quote`), accounting for Windows paths (`\`, drive-letter
  `:`). The document could previously be invalid SARIF (simply never
  caught by the existing tests: `jsonschema.validate()` without an
  explicit `FormatChecker` doesn't enforce the `format: uri-reference`
  constraint).

### Fixed
- `--tui`: any scanned content (a file name, object name, snippet,
  message) landing in `Static.update()`/`DataTable.add_row()` as a plain
  string got parsed by Textual as its own markup — a square bracket in
  real code or a path (`arr[i][j]`, `notes[archive]`) could crash with a
  markup error or corrupt the output. All such text now gets wrapped in
  `rich.text.Text(...)`, the same technique already used in
  `terminal_report.py`.
- `--save`/`--baseline` pointing at the same file used to silently
  overwrite the snapshot and compare a run against itself — now an
  explicit error (compared by resolved path, also catches two different
  spellings of the same file).
- `--save` no longer writes a baseline snapshot if the scan was partial
  (there were file-read errors) — such a snapshot isn't a reliable
  reference point for a later `--baseline`.
- `--explain` only checked for a conflict with some of the scan flags
  (`--fail-on`, `--save`, `--baseline`, `--check-connect-by`) — it now
  also accounts for `--verify`, `--format`, `--output`, `--severity`,
  `--object`, and the error text lists all of them.
- `load_baseline()` required the full set of JSON Schema fields on every
  finding entry — old `--save` snapshots saved before `gap_number`/
  `failure_stage` existed got rejected. Now only the fields actually used
  without `.get()` are required (`group_key`, `detector`).
- Several places read a file via `read_text(errors="replace")` with no
  explicit encoding — on a platform with a non-UTF-8 locale this could
  read the file in the wrong encoding instead of an honest UTF-8 +
  replacement characters on invalid bytes.
- `package_state`: the detector only looked at declarations in a
  `PACKAGE BODY` and skipped `CONSTANT` — both cases get the same broken
  `set_config`/`current_setting` rewrite from ora2pg in practice as an
  ordinary variable (confirmed against a real ora2pg 25.0 run, see
  `docs/research/gap-036-package-state.md`). On the real `logger.pkb`
  from the test corpus, this was 22 uncounted findings.
- `recursive_with`: `WITH seed AS (...), tree AS (...)`, a recursive CTE
  that isn't first in the `WITH` list, wasn't detected at all, because
  the regex required the `WITH` keyword directly before the CTE name.
- `bulk_collect`: the "is this a local TYPE declaration, not a
  schema-level `CREATE TYPE`" check rescanned the entire file prefix
  again on every match, O(n²) on a file with many local `TYPE`
  declarations. Replaced with a single forward pass building a position
  set.

## [0.7.0] - 2026-08-20

### Added
- `examples/end-to-end/` — a reproducible run through the whole SCAN →
  migrate → VERIFY lifecycle on one real example (GAP-003, `BULK
  COLLECT`/`FORALL`/a local `TYPE`): real `ora2pg 25.0` output
  (`generated/`), a manually fixed version (`generated_fixed/`), both
  confirmed against a real PostgreSQL 16 server (creating the procedure
  succeeds in both cases, but `CALL` only fails on the unfixed one, at
  the exact line the research doc describes), a `--save` snapshot and
  both `--verify` runs (`STILL_PRESENT` before the fix, `NOT_DETECTED`
  after) saved as files, `run_demo.sh` reruns all of it and checks the
  `--fail-on` exit code. The example's own README separately explains
  why `--verify` doesn't collapse into a single PASS/FAIL, the same
  principle as `NOT_VERIFIABLE`: the `--fail-on` gate only exists before
  migration, `--verify` is an honest, re-checkable answer, not a stamp.
- `docs/tui_demo.gif`/`docs/tui_demo.ru.gif` — a GIF of the interactive
  mode in the README next to the regular `docs/demo.gif`: scanning,
  comparing against a baseline (real NEW/RESOLVED/UNCHANGED, computed
  from the first and second half of the same real example file, not
  made-up numbers), and a finding's full explanation on click. Rendered
  the same way as the regular demo.gif — a real `App.run_test()` +
  `export_screenshot()` + Playwright + Pillow, EN/RU variants same as
  that one.
- `--tui` now covers the same ground as the regular flag-based workflow,
  not just scanning and browsing: multi-path selection ("Add to
  selection"/"Clear selection" buttons — scans all accumulated paths at
  once, deduplicated by file if the same file is reachable both directly
  and via a selected directory), an optional "Check CONNECT BY" check
  (the same as `--check-connect-by`, the same graceful warning when
  ora2pg isn't installed), a baseline-file field on the scan screen
  (comparison uses the same NEW/RESOLVED/UNCHANGED counters as
  `--baseline`, plus a "Save baseline" button on the results screen,
  the equivalent of `--save` — saves the full, unfiltered finding list,
  not whatever the severity select filtered, same as the CLI), and a
  "Verify mode" — the same post-migration STILL_PRESENT/NOT_DETECTED/
  NOT_VERIFIABLE breakdown by detector as `--verify`, on its own screen
  with the same conflict logic (verify can't be combined with the
  CONNECT BY check, requires a baseline to be set). Testing through
  Pilot turned up a real test-harness bug unrelated to the new code: a
  button click right after `isinstance(app.screen, ...)` becomes true
  can miss — Textual doesn't guarantee the new screen's layout has
  settled by that point, and the click lands on the "^p palette" hint in
  the footer instead, opening the command palette instead of pressing
  the button; `_wait_until()` in `tests/test_tui_app.py` now does one
  extra `pause()` after the condition becomes true instead of returning
  immediately.
- `--tui` — an interactive screen built on [`textual`](https://github.com/Textualize/textual):
  pick a file/directory in a tree with mouse or keyboard,
  severity/language via dropdowns, scan with a button, click a row in
  the findings table to open a panel with the full explanation (message,
  `GAP-NNN`, when it breaks — the same info `--explain` and the terminal
  report already show). An optional extra
  (`pip install "ora2pg-gap-report[tui]"`) — `textual` isn't part of the
  base install, the regular flag-based CLI works exactly as before
  without it; running `--tui` without the extra installed gives a clear
  install hint instead of a traceback (checked as a separate CI step
  against a clean wheel install, without `[dev]`/`[tui]`). Standalone
  mode, like `--explain`/`--verify` — can't be combined with the scan
  flags and takes at most one path. The first version is a deliberately
  narrow slice: scanning and browsing only, no `--save`/`--baseline`/
  `--verify`/`--check-connect-by` from inside the TUI and no multi-path
  selection, expanding as real usage calls for it, not all at once.
  Styled with the Dracula theme (one of `textual`'s built-in themes) —
  the severity colors come from its own published palette rather than
  separately picked named rich colors, to stay consistent with the
  overall theme; chosen from `textual`'s 6 built-in themes (Nord,
  Gruvbox, Dracula, Catppuccin Mocha, Tokyo Night, the default) after
  visually comparing the same screen under each — the first version used
  Nord, but the choice changed to Dracula after that comparison. Found
  and fixed via an actual screenshot, not just tests: the findings table
  used to show the full path in the File column, pushing Detector/GAP
  off the edge of the screen — now just the filename; the `GAP-NNN`/
  stage line in the detail panel used to sit after the explanation text
  and would run off the visible area for long explanations — now right
  under the heading; the detail panel's fixed height didn't fit in a
  small terminal alongside the rest of the layout — now proportional
  (`fr`) instead of absolute.
- `gap_number`/`failure_stage` now show up everywhere a finding does, not
  just `--explain`: two new columns in `--format markdown`/`html`, two
  new keys in `--format json`/`csv`, and a `properties` bag
  (`gapNumber`/`failureStage`) on each SARIF rule. The terminal report's
  "Пояснения" panel gets a dim `GAP-NNN · <stage>` line per detector
  group. `--save` snapshots carry both fields too now (old snapshots
  without them still load fine — nothing reads them for `--baseline`/
  `--verify` matching). Both `schemas/report.schema.json` and
  `schemas/baseline.schema.json` updated and kept identical for shared
  fields, per `tests/test_schemas.py`'s own enforcement. `gap_number` is
  `null` for a detector with no registered gap (e.g. `dbms_utl_calls`);
  `failure_stage` is additionally `null` for the two gaps in
  `FAILURE_STAGE_EXEMPT_DETECTORS`.
- `.github/workflows/publish.yml`: a new `offline-bundle` job — on a
  release publish, automatically builds
  `ora2pg-gap-report-offline.tar.gz` (base install, without `--oracle` —
  `oracledb`'s platform-specific wheels aren't guaranteed to match the
  target machine) and attaches it as a GitHub Release asset.
- `README.md` is now in English (the primary one, shown by default on
  GitHub/PyPI), the previous Russian content moved to `README.ru.md`,
  both with a language switcher at the top. `pyproject.toml`'s
  `description` was translated too — it used to be in Russian while
  GitHub's About and the PyPI page were out of sync on language. The
  deeper docs (`ARCHITECTURE.md`/`DEVELOPMENT.md`/`CONTRIBUTING.md`)
  stayed Russian-only for now.
- `docs/demo.gif` is now in English (for the new English README), the
  previous Russian version is kept as `docs/demo.ru.gif` and used by
  `README.ru.md`.
- `ROADMAP.md` — where the project could grow, with an honest split into
  "already implemented" / "near-term" / "backlog with no deadlines and no
  guarantees" and an explicit rule: an item only gets picked up once
  there's a confirmed practical reason, not "that would be cool."
- `docs/ci-integration.md` — a pipeline alongside `ora2pg` (a gate before
  conversion, `--check-connect-by`, `--verify` after) and a sample GitHub
  Actions workflow: `--format sarif` + `upload-sarif` gets findings
  inline in the PR via native GitHub code scanning, no custom Action or
  bot needed.
- `docs/verification-capability-matrix.md` — for each of the 37 gaps,
  explicitly which `--verify` mode it has (`verbatim`/`not_verifiable`/
  `generated_only`) and why; cross-checked line by line against
  `VERIFICATION_MODE` and the gap registry by a script, not written by
  eye.
- `GapEntry.failure_stage` (`gap_registry.py`) — at which stage a gap
  actually becomes visible: `deployment`/`runtime`/`semantic`
  (`conversion` is defined in `FAILURE_STAGES` but has never been
  needed, see `docs/failure-stage-notes.md`). Rolled out to all 37 gaps:
  a trial run on 10 first, then the remaining 27 — every value taken
  from the gap's own research doc, not made up. Two exceptions with no
  stage — `autonomous_tx` and `object_type`
  (`FAILURE_STAGE_EXEMPT_DETECTORS`): their finding isn't about the
  shape of the code, it's about an underestimated/missing number in
  `--estimate_cost`/`SHOW_REPORT`. The full rollout uncovered that
  `connect_by_nocycle` is the sole exception to the "`CREATE PROCEDURE`
  always pushes the failure to the first call" pattern: the conversion
  structurally breaks the block badly enough that PostgreSQL's parser
  trips up right at load time, before `check_function_bodies = false`
  even applies. Shown in `--explain` as a "Когда ломается"/"Fails at"
  line. `doctor.py` now requires full coverage (except the two
  exceptions), not just validity of the values that are set.

### Fixed
- The English footnote text about the rough effort estimate (`markdown`/
  `html` formats) had linked to README.md as "Russian-only for now" for
  years — stale ever since the README got translated to English; now
  links to the actual section heading ("Why almost everything is `high`").

### Changed
- `terminal_report.py`: the `→` character in the banner and the
  "Рекомендации" section's hints was replaced with the ASCII `->` — on
  some terminals/fonts (especially in closed corporate environments
  without a full Unicode glyph set), that character renders poorly or
  not at all.
- `docs/demo.gif`/`docs/demo.ru.gif` regenerated — the old versions
  didn't show the `GAP-NNN · <stage>` line in the explanation panel
  (added later) and still used `→` instead of `->`. `docs/social-
  preview.png` was regenerated too, now in English (tagline and badges
  synced with README/GitHub About/PyPI already being English; there's no
  point making an RU/EN pair for the social-preview image, GitHub only
  stores one per repository, unlike demo.gif). **`docs/social-
  preview.png` needs to be manually re-uploaded via Settings → General
  → Social preview, GitHub doesn't pick the file up from the repository
  automatically.**

## [0.6.0] - 2026-08-18

### Added
- `.github/workflows/publish.yml` — publishing to PyPI via
  [Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
  (OIDC) when a full (non-pre-release) GitHub Release is published: no
  PyPI token stored in repository secrets. Requires a one-time setup on
  PyPI's side (Your projects → Publishing → Add a new publisher,
  owner/repo/workflow file `publish.yml`/environment `pypi`).
- Nine newly confirmed gaps (GAP-029..037), the registry grew from 28 to
  37 (a real ora2pg 25.0 + PostgreSQL 16 run for each):
  - `rowid_type` (GAP-029) — `ROWID`/`UROWID` as a column type converts
    to an incompatible `oid`.
  - `sequence_cycle` (GAP-030) — `CREATE SEQUENCE ... CYCLE` loses the
    `CYCLE` clause, `NEXTVAL` fails once the range is exhausted.
  - `default_on_null` (GAP-031) — `DEFAULT ON NULL` is copied verbatim,
    a syntax error right at `CREATE TABLE`.
  - `public_synonym` (GAP-032) — `CREATE [PUBLIC] SYNONYM` loses the
    target object's schema, and on a name collision becomes a
    self-referencing `VIEW`.
  - `virtual_column` (GAP-033) — `GENERATED ALWAYS AS (...) VIRTUAL`
    loses `ORA-54016`'s protection against explicit assignment.
  - `nested_subprogram` (GAP-034) — a local nested procedure/function
    "leaks" out as a separate object, its body gets corrupted.
  - `conditional_compilation` (GAP-035) — `$IF`/`$ELSIF`/`$ELSE`/`$END`
    directives are copied verbatim, PL/pgSQL has no such preprocessor.
  - `package_state` (GAP-036) — a package variable is replaced with
    `set_config()`/`current_setting()` with no type cast and no
    `missing_ok`.
  - `index_organized_table` (GAP-037) — `ORGANIZATION INDEX` (IOT) gets
    dropped, the table becomes a regular heap with a separate index.
- `CODE_OF_CONDUCT.md`, `SECURITY.md` — close out the GitHub Community
  Standards checklist.

### Changed
- README: the static `docs/screenshot.svg` replaced with `docs/demo.gif`
  — an animation of a real scan, rendered via `terminal_report.render()`
  on real findings. Added `docs/social-preview.png` (1280×640) for the
  repository card.

## [0.5.0] - 2026-08-17

### Changed
- `estimate_hours()` no longer sums the hour range for every finding
  independently — now only the first occurrence of each detector gets
  the full severity-based range, and every repeat occurrence of the same
  detector gets a separate, flat "apply an already-understood fix" range
  (0.25-1h, independent of severity). 8 `autonomous_tx` findings in one
  package used to be counted as 8 independent high-severity tasks (16-64h
  just for those), even though it's one learned pattern (the dblink
  wrapper) applied 8 times. On `logger.pkb` + `logger.pks` (28 findings),
  the estimate changed from ~38-152h to ~11-45h. The terminal panel's
  "Оценка ручной доработки" now shows a separate `N patterns from M
  findings` line whenever they diverge — a new
  `distinct_detector_count()` in `effort_estimator.py`.

### Documentation
- Documented four real limitations that hadn't been explicitly written
  down anywhere before (found by an outside line-by-line review, each
  confirmed separately, not taken on faith): `dbms_utl_calls._CONVERTED`
  is a list tied to a specific `ora2pg` version, needing manual upkeep
  when `ora2pg` is updated, not checked automatically; `ora2pg_wrapper.py`
  parses `--estimate_cost` against `ora2pg`'s exact textual output
  format, which isn't an officially stable interface for it;
  `oracle_connector.export_schema()` only exports `PACKAGE BODY`/
  `TRIGGER`, standalone procedures/functions, views, and types aren't
  exported automatically (though they're analyzed correctly if their DDL
  is fed in as a file); dynamic SQL visibility
  (`mask_dynamic_sql_visible()`) doesn't track SQL assembled into a
  variable piece by piece across several statements before `EXECUTE
  IMMEDIATE`, and doesn't support the old `DBMS_SQL.PARSE`/`EXECUTE` API
  at all.

### Added
- `--verify` — post-migration static verification: compares pre-migration
  findings (a `--save` snapshot) against what's actually left in the
  already-generated ora2pg PostgreSQL code. Not a functional/behavioral
  check — it never connects to anything, never executes anything, it
  just reruns the same detectors against the generated file. Compared at
  detector granularity, not per finding (file/object/snippet matching,
  like `--baseline` uses, doesn't survive the Oracle→PostgreSQL boundary:
  `ora2pg` renames objects, the file is different either way). New
  `verification.py` module: 13 detectors whose finding `ora2pg` copies
  into the output essentially unchanged (`cross_apply`, `json_table`,
  `identity_column`, and others — full list in `docs/ARCHITECTURE.md`)
  are marked `VERBATIM` — for these, re-running the detector against the
  output is meaningful: `STILL_PRESENT`/`NOT_DETECTED`. 15 detectors
  whose finding `ora2pg` either drops entirely or mangles the
  surrounding structure enough that re-detection can't be trusted are
  marked `NOT_VERIFIABLE` — for these, `NOT_DETECTED` would be a
  tautology (the construct is guaranteed to be absent from the output on
  any migration, regardless of whether anyone fixed the problem by hand),
  not a signal. `connect_by` doesn't participate — it already only
  analyzes generated code. `--format terminal`/`--format json`;
  `doctor.py` checks that every detector is classified.

### Added
- `--lang en` / `--set-lang` / `ORA2PG_GAP_REPORT_LANG` — English output
  as an option, Russian stays the default (doesn't change without an
  explicit action — no existing script/CI parsing the current Russian
  output breaks). `--set-lang` opens an interactive language picker (a
  styled rich panel, `[1] English`/`[2] Русский`) and saves the choice to
  `~/.config/ora2pg-gap-report/language` (or `$XDG_CONFIG_HOME`) for all
  future runs; the same picker shows itself once on the first run in an
  interactive terminal if the language isn't set anywhere yet. Priority:
  `--lang` → env var → saved choice → interactive picker → Russian. New
  `ora2pg_gap_report/i18n.py` module: every UI string in the terminal/
  markdown/HTML report, all runtime error messages and warnings, plus an
  English translation of each of 29 detectors' explanation and
  recommendation (`EXPLANATION_EN`, keyed by the Russian finding text
  itself, not the detector name, because `bulk_collect` has three
  different messages under one detector). The translation is substituted
  once, centrally, before findings reach any output format — json/csv/
  sarif don't need their own translation logic. `--help` and the content
  of `docs/research/*.md` (including what `--explain` prints) stay in
  Russian — both deliberately out of scope for this change, see
  `i18n.py`. `doctor.py`: a new check — every detector message constant
  must have a translation in `EXPLANATION_EN` (otherwise `--lang en`
  would silently fall back to Russian for that finding, with nothing
  reported about it).

### Fixed
- Four dangling references to a nonexistent `PROJECT_BRIEF.md` (`cli.py`,
  `report_generator.py`, `effort_estimator.py`, `oracle_connector.py`) —
  replaced with links to the actual sections of `README.md`/
  `docs/ARCHITECTURE.md` (issue #1).

### Added
- `GapEntry` (`gap_registry.py`) gained `ora2pg_version`/
  `postgresql_version` fields — which versions a finding was actually
  confirmed against (defaulting to `25.0`/`16`, as was already the case
  for all 28 so far, but the data structure is now ready for different
  versions on future findings without editing every record at once).
  `--explain` now prints this version. `docs/research/GAP_REGISTRY.md`
  gained a PostgreSQL column (the PostgreSQL version used to live only
  in `AUDIT.md`'s general note, not per row). `doctor.py` cross-checks
  `GAP_REGISTRY.md`'s columns against `gap_registry.py` — the same class
  of check as the detector file tree, just for versions.

### Changed
- README.md (540 lines) split up: the internal architecture (lexer,
  masking, attribution, dynamic SQL handling, file layout) moved to
  `docs/ARCHITECTURE.md`, testing/corpus/live-Oracle content moved to
  `docs/DEVELOPMENT.md`. README stays about "what this is and why" — the
  problem, the detectors, install, usage. `doctor.py` updated to match:
  the detector file-tree check now cross-checks `docs/ARCHITECTURE.md`
  against disk, not README.md.

### Added
- `doctor.py`: a new check — the detector file tree in README.md
  ("Архитектура") is cross-checked against the real file list in
  `ora2pg_gap_report/detectors/` in both directions (a stale entry or a
  missing file are both errors). Closes exactly the class of problem
  that had left README claiming "three of four detectors" for a while
  before this release, even though there were already 29.
- The README now documents `severity` criteria (26 of 28 registered gaps
  are `high`, `dbms_utl_calls` — the 29th detector, not tied to a
  specific GAP-NNN — is also `medium`; not an artificially engineered
  distribution) and gained an intro diagram/quick start at the very top
  of the file.

- The real open-source-code registry expanded from four projects to
  seven: added `method5/plsql_lexer` (a PL/SQL lexer/tokenizer, with
  nonstandard `.plsql`/`.bdy`/`.spc` file extensions), `mbleron/ExcelGen`
  (an Excel-file generator), and `osalvador/tePLSQL` (a templating engine
  that makes heavy use of `EXECUTE IMMEDIATE`). A fresh count across all
  seven together: **247,298 lines**, 0 false positives, 0 crashes,
  including two files where `EXECUTE IMMEDIATE` genuinely builds code
  dynamically, without ever triggering a false attribution. The number of
  corpus-validated detectors grew from 8 to 9 — `with_function` got
  confirmed against real open-source code for the first time (`WITH
  FUNCTION` inside `mbleron/ExcelGen`'s test suite), locked in with a
  regression test on the real fragment. See `docs/research/AUDIT.md`.
- `--format html` — a self-contained HTML page (inline CSS, no external
  CSS/JS/fonts, works offline like the other formats, see the "Install
  without internet access" section), for showing the report to a
  client/manager without installing anything. Same summary (severity
  counts, the same rough hour estimate with the same "uncalibrated
  heuristic, not a measurement" warning as markdown/terminal) and the
  same findings table as the other formats, with severity color coding.
  All dynamic content (file paths, object names, messages) is escaped
  via `html.escape()`.
- Visibility of constructs hidden inside `EXECUTE IMMEDIATE` (a single
  string literal or a `'...' || expression || '...'` concatenation). 14
  detectors that use the shared attribution index (`bulk_collect`,
  `connect_by_nocycle`, `cross_apply`, `database_link`,
  `flashback_query`, `insert_all`, `json_table`, `merge_delete_clause`,
  `model_clause`, `oracle_text`, `pivot_clause`, `recursive_with`,
  `sql_macro`, `with_function`), plus `autonomous_tx` separately (its own
  procedure-boundary tracking mechanism, not the shared index) now use a
  new function, `plsql_lex.mask_dynamic_sql_visible()` — a second,
  separate masking flavor in which the `EXECUTE IMMEDIATE` argument stays
  visible instead of being blanked out. The "which object surrounds this
  position" index is still always built from the safe, fully masked text
  — otherwise a package/procedure the code creates dynamically at
  runtime would get mistaken for a real object declared in the source
  tree, and would corrupt the attribution of unrelated findings.
  Confirmed against real open-source code (`utPLSQL`): found and
  correctly attributed to the real procedure findable in the source
  tree — a hidden `PRAGMA AUTONOMOUS_TRANSACTION` (inside a dynamically
  created package, `run_helper.pkb`) and a hidden `BULK COLLECT INTO`
  (inside a dynamically executed anonymous block, `coverage_helper.pkb`)
  — both locked in with regression tests on the real fragments. Not
  covered: schema-level detectors (`table_partitioning`,
  `external_table`, `invisible_column`, etc., including the part of
  `oracle_text` that handles `CREATE INDEX ... INDEXTYPE`) still don't
  see the same-named DDL construct if it's built dynamically — honestly
  out of scope for this change, see README.md, "Constructs hidden inside
  dynamic SQL."
- `--save PATH` / `--baseline PATH` — a snapshot of the current run's
  findings and a comparison against the next one (NEW/RESOLVED/
  UNCHANGED), for tracking migration progress across runs. Findings are
  matched by a stable fingerprint (detector + file + object + snippet),
  not by line number. Both flags always work against the full finding
  set, independent of `--severity`/`--object`.
- `--fail-on high|medium|low` — exit code `1` if there's at least one
  finding at that severity or above, for a CI gate. Also evaluated
  against the full finding set, not what's left after
  `--severity`/`--object`.
- `--explain GAP-NNN` — prints a specific gap's research doc straight to
  the terminal, without scanning any files. In the pip package (where
  `docs/research/` isn't shipped), shows a direct link to the document on
  GitHub instead of the text — confirmed by building a real wheel and
  running from a clean venv outside the repository, not just a unit test.
- `ora2pg_gap_report/gap_registry.py` — a single source of truth for all
  28 gaps (number, detector, test files), used by `--explain` and
  `scripts/audit_gap_test_counts.py` (which used to keep their own
  separate list).
- `scripts/doctor.py` — a registry integrity check: every GAP-NNN has a
  research doc, a detector, and tests (including at least one positive
  test and at least one guard test). Now part of CI (the `lint` job) — a
  registry drifting from the files on disk breaks the build right away.
- `--format csv` — a flat finding dump for analysts/spreadsheets, the
  same fields and order as `--format json`.
- `schemas/report.schema.json` and `schemas/baseline.schema.json` —
  formal JSON Schemas for `--format json` and the `--save`/`--baseline`
  files, checked in tests against the tool's real output
  (`tests/test_schemas.py`), not just written by hand. `jsonschema` is a
  new dev dependency (only for this check in tests, not for the CLI
  itself).
- `--format sarif` — SARIF 2.1.0 for GitHub code scanning / GitLab SAST.
  Severity mapped to SARIF levels (high → error, medium → warning, low →
  note), one rule per detector that actually fired, with a link to the
  research doc (`helpUri`) if the detector is in the GAP-NNN registry.
  Checked in tests against the official OASIS SARIF 2.1.0 schema
  (`tests/test_sarif.py`, schema kept in `tests/fixtures/`).

### Fixed
- README: the "Архитектура" section described the architecture of a
  version with four detectors (`autonomous_tx`/`compound_triggers`/
  `dbms_utl_calls`/`connect_by`) — stale text left over from v0.1.0,
  even though the rest of the same file already listed all 28. Rewritten
  honestly: `connect_by` is the only detector that needs `ora2pg`
  installed, the other 27 are plain Python with no external dependencies.

### Changed
- The real open-source-code registry used to validate detectors expanded
  from two projects to four: added `utPLSQL/utPLSQL` (the PL/SQL
  unit-testing framework) and `OraOpenSource/Logger` (the canonical
  logger). Combined across all four: **215,214 lines** (an exact, fresh
  count across all four repositories together at the time of this check,
  not a sum of separately remembered numbers for each — the repositories
  are alive and growing, and the previous ~143k estimate for the first
  two had no pinned commit to anchor it to). The number of
  corpus-validated detectors grew from 5 to 8 (`autonomous_tx`,
  `global_temp_table`, `collection_type` added) — each with a new
  permanent regression test on a real fragment. The only finding: an
  honestly documented boundary of applicability, `object_name='UNKNOWN'`
  on an anonymous `declare...begin...end;` block (an install script, not
  a `DBMS_METADATA.GET_DDL` object export) — not a bug, zero false
  positives and zero crashes across the whole expanded corpus. See
  `docs/research/AUDIT.md`.

## [0.4.0] - 2026-08-16

### Added
- 7 new detectors, GAP-022..GAP-028. The registry is now 28 confirmed
  gaps, see `docs/research/GAP_REGISTRY.md`:
  - `cross_apply` — `CROSS APPLY`/`OUTER APPLY`, the `APPLY` syntax
    doesn't exist in PostgreSQL at all.
  - `oracle_text` — the `INDEXTYPE IS CTXSYS.*` (Oracle Text) domain
    index is dropped entirely; `CONTAINS`/`CATSEARCH`/`MATCHES` calls
    don't get carried over.
  - `recursive_with` — a native recursive `WITH ... AS (...)` (not via
    `CONNECT BY`) missing PostgreSQL's mandatory `RECURSIVE` keyword.
  - `invisible_index` — an `INVISIBLE` index loses its invisibility to
    the optimizer.
  - `read_only_table` — `CREATE TABLE ... READ ONLY` loses its
    immutability guarantee; `INSERT` succeeds where Oracle would
    guaranteed-block it (`ORA-12081`).
  - `materialized_view_log` — `CREATE MATERIALIZED VIEW LOG` isn't
    converted at all, only a trace in the DEBUG log.
  - `identity_column` — `GENERATED ... AS IDENTITY (...)` with options: a
    genuine double-paren bug in ora2pg's own substitution (not a missed
    conversion, a broken one — the code fails to load the DDL at all).
- `docs/research/AUDIT.md` and `scripts/audit_gap_test_counts.py` updated
  for all 28 gaps.

### Fixed
- A systemic statement-scoping bug: `DBMS_METADATA.GET_DDL` (this same
  project uses it to export DDL from Oracle) doesn't put a `;` at the end
  of a statement by default, and some detectors scoped "their" statement
  as "up to the next `;`, or the end of the file if there isn't one," so
  a construct from a later table could get misattributed to an earlier,
  unterminated one. This affected already-published `table_partitioning`
  and `external_table` too, not just this release's new detectors. Added
  a shared `statement_end()` helper in `plsql_lex.py`, applied across 8
  detectors: `table_partitioning`, `external_table`, `invisible_column`,
  `global_temp_table`, `oracle_text`, `invisible_index`,
  `read_only_table`, `identity_column`.
- `invisible_index`/`read_only_table`: false positives on a column with
  the same name as the modifier (`invisible`/`read_only` as a column
  identifier, including double-quoted) are now excluded.
- `invisible_index`/`read_only_table`/`oracle_text`: a finding's line
  number now points at the modifier/clause itself (`INVISIBLE`/`READ
  ONLY`/`INDEXTYPE IS ...`), not the line with the opening `CREATE
  TABLE`/`CREATE INDEX` — matters for multi-line DDL.
- `materialized_view_log`: severity raised from `medium` to `high` — the
  same risk profile as `table_partitioning`/`external_table` (the
  construct silently disappears with no PostgreSQL error, but represents
  a real architectural loss).

## [0.3.0] - 2026-08-15

### Added
- 14 new detectors, GAP-008..GAP-021: `pivot_clause`, `object_type`,
  `with_function`, `flashback_query`, `global_temp_table`,
  `table_partitioning`, `connect_by_nocycle`, `context_object`,
  `insert_all`, `json_table`, `external_table`, `sql_macro`,
  `invisible_column`, `collection_type`. The registry is now 21 confirmed
  gaps, see `docs/research/GAP_REGISTRY.md`.
- A `--version` flag.
- Support for directories as an argument — recursively finds
  `.sql`/`.pks`/`.pkb` files, not just an explicit file list.
- `docs/research/AUDIT.md` — a summary check of the evidence behind each
  of the 21 gaps (research doc, real ora2pg output, expected/actual,
  tests, including guard tests against false positives), plus
  `scripts/audit_gap_test_counts.py`, which recomputes those numbers.
- `ruff` — a lint job in CI (with an explicitly pinned rule set, not the
  implicit default, see `[tool.ruff.lint]` in `pyproject.toml`).

### Fixed
- Finding attribution (`object_name` in the report) for real code, not
  just synthetic examples — found by running the tool against two large
  open-source PL/SQL codebases (`mortenbra/alexandria-plsql-utils`,
  `oracle-samples/db-sample-schemas`, ~143k lines combined):
  - A `PACKAGE` spec (without `BODY`) and `CREATE VIEW`/`CREATE
    MATERIALIZED VIEW` are now recognized as attribution containers —
    findings inside them used to fall into `UNKNOWN`.
  - A `CREATE` construct inside a `GRANT`/`REVOKE` privilege list
    (`GRANT ..., CREATE VIEW TO oe;`) is no longer mistaken for an actual
    object declaration.
  - SQL*Plus line comments (`REM`/`REMARK`) are now masked — a real
    declaration preceded only by such comments used to be able to lose
    its attribution.
- `table_partitioning`: a partitioned index (`CREATE INDEX ... GLOBAL
  PARTITION BY RANGE ...`) is no longer attributed to a random unrelated
  table; added support for `REFERENCE`/`SYSTEM` strategies.
- `insert_all`: the search window for `INTO` after `INSERT ALL`/`FIRST`
  was widened — it used to miss the finding with a long `WHEN` condition.
- `invisible_column`: `INVISIBLE UNIQUE`/`INVISIBLE PRIMARY KEY` and other
  inline constraints after the modifier are now flagged too.
- `bulk_collect`: a schema-level `CREATE TYPE ... EDITIONABLE ... IS
  TABLE OF` no longer gets duplicated as this detector's own finding.
- Directories: a file reachable both directly and via a directory
  (`schema/ schema/logger.pkb`) is no longer counted twice; file
  extensions (`.SQL`/`.PKB`) are matched case-insensitively.

## [0.2.0] - 2026-08-14

### Added
- GAP-002 `merge_delete_clause` — `MERGE ... DELETE WHERE`.
- GAP-003 `bulk_collect` — `TYPE ... IS TABLE OF` / `BULK COLLECT INTO` /
  `FORALL`.
- GAP-006 `database_link` — `table@dblink_name`.
- GAP-007 `model_clause` — `MODEL PARTITION BY ... MEASURES ... RULES`.
- A completely reworked terminal report (`rich`): a banner, a summary
  panel, a "objects with the most findings" tree, a recommendations
  section per triggered detector, an effort-estimate panel (best/
  average/worst case).
- `--severity` and `--object` flags for filtering findings in the report.
- `docs/research/GAP_REGISTRY.md` — a formalized gap registry with the
  `ora2pg` version each was confirmed against and a status
  (`confirmed`/`fixed-upstream`/`wont-fix`).
- A PyPI badge in the README.

## [0.1.0] - 2026-08-14

First release.

### Added
- GAP-001 `autonomous_tx` — `PRAGMA AUTONOMOUS_TRANSACTION`,
  underestimated cost in `SHOW_REPORT`/`--estimate_cost`.
- GAP-004 `compound_triggers` — `COMPOUND TRIGGER`, ora2pg's file parser
  silently fails on it.
- GAP-005 `connect_by` — a `LEVEL`-substitution bug in the generated
  `WITH RECURSIVE` (optional, `--check-connect-by`, requires ora2pg).
- `dbms_utl_calls` — a classifier for specific `DBMS_*`/`UTL_*` calls.
- CLI: `--format` (terminal/markdown/json), `--output`.
- Exporting DDL directly from Oracle: `ora2pg-gap-export`.
