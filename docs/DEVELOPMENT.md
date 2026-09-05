*English | [Русский](DEVELOPMENT.ru.md)*

# Development

How to verify changes, what real-code corpus is used, how to confirm a
new detector against a live Oracle. For "what this is and why," see
[README.md](../README.md); for the internal architecture, see
[ARCHITECTURE.md](ARCHITECTURE.md).

## How a new detector gets added

This project doesn't try to find a detector for every Oracle-specific
construct. `ROWNUM`, `DECODE`, `NVL`, `SYSDATE`, `%TYPE`, sequences,
standard exception semantics — `ora2pg` converts all of these correctly,
and no detector is needed for them no matter how exotically Oracle-ish
they sound.

A new detector only shows up after the hypothesis has been confirmed in
practice:

1. Pick a specific Oracle construct.
2. Build a minimal reproducible example.
3. Run the example through a real `ora2pg`.
4. Check the generated PostgreSQL code for correctness.
5. If `ora2pg` handled it fine, the hypothesis is rejected, no detector
   gets added. If a real, reproducible bug turns up, a test fixture is
   added and the detector gets written.

This is how, for example, the initial hypothesis about `CREATE PACKAGE`
got filtered out — an obvious-looking candidate at first glance, but in
practice `ora2pg` carries it over fine (`docs/research/step0-show-report-
baseline.md`). And this is how `COMPOUND TRIGGER` and the `LEVEL` bug in
`CONNECT BY` got confirmed — both reproduced against a real `ora2pg` run,
not assumed from a description.

Every confirmed finding is numbered and collected in
[`research/GAP_REGISTRY.md`](research/GAP_REGISTRY.md) — each row states
which detector covers it and which `ora2pg` version it was confirmed
against. [`research/AUDIT.md`](research/AUDIT.md) is a summary check of
the evidence behind every confirmed gap (research doc, real ora2pg
output, expected/actual, tests, including guard tests against false
positives).

## Writing the detector itself

Once a gap is confirmed, most detectors are a spec rather than a
function. `ora2pg_gap_report/detector_spec.py` holds the shared scanning
code; a detector module declares what varies and calls `build()`:

```python
SPEC = DetectorSpec(
    name="read_only_table",
    dialect="oracle",
    severity="high",
    pattern=_READ_ONLY_RE,
    strategy=STATEMENT_CLAUSE,
    snippet="READ ONLY",
    statement_pattern=_TABLE_RE,
)

find_read_only_tables = build(SPEC, plsql_lex)
```

There are five strategies, because detectors really do scan in five
different ways:

| strategy | scans | attributes the finding to |
|---|---|---|
| `ENCLOSING` | the whole masked source | the routine containing the match |
| `MATCH_NAMED` | the whole masked source | the object the match itself names |
| `TABLE_COLUMNS` | each `CREATE TABLE`'s column-definition list | the table |
| `TABLE_STATEMENT` | each `CREATE TABLE`'s whole statement | the table (once per match) |
| `STATEMENT_CLAUSE` | each statement `statement_pattern` finds | that statement (at most once) |

`search_mask` picks which masked view the pattern runs over — use
`MASK_DYNAMIC_SQL_VISIBLE` when the construct also matters inside an
`EXECUTE IMMEDIATE` literal. `anchor_mask` stays at its default: line
numbers and routine names come from the fully masked view, which is the
one that indexes them correctly.

About a third of the detectors are still plain functions, and should be.
Write a function rather than a spec when the detector needs more than one
pass over the source, builds its object name from more than the match,
emits more than one message, or tests a condition no pattern expresses.
The rule of thumb: if it fits a strategy as it stands, write a spec; if
making it fit would mean adding a flag to `DetectorSpec`, write the
function.

Either way the message text lives in `ora2pg_gap_report/messages.py`,
keyed by the detector's own name, with both `ru` and `en`. `doctor.py`
checks that every detector's message id exists and that no message is
left orphaned.

## Tests that run the real ora2pg

Most of this suite tests this project's own code against ora2pg behaviour
recorded by hand in `docs/research/`. `tests/test_real_ora2pg.py` is the
part that checks the recording still holds: `ora2pg_wrapper.py` parses
ora2pg's `--estimate_cost` output by matching its exact comment wording,
and a release that rewords it makes those regexes match *nothing* rather
than raise — a silent zero indistinguishable from a clean package.

They are marked `ora2pg` and skip when the binary isn't on PATH, so a
developer without a Perl toolchain still gets a green suite:

```sh
pytest -m ora2pg          # just those, if you have ora2pg installed
pytest -m "not ora2pg"    # everything else
```

CI runs them in their own job with ora2pg built from source, pinned to
the version `gap_registry.py` records its findings against. One of the
tests asserts those two agree, so bumping the CI version without
re-verifying the gaps fails loudly instead of quietly testing the parsers
against output nobody reviewed. The job also fails if the tests *skip* —
a marker-selected job that installs nothing would otherwise pass green
while running no tests at all.

## Registry integrity (doctor)

The registry (`ora2pg_gap_report/gap_registry.py`) and the file layout
are checked automatically:

```sh
python3 scripts/doctor.py     # every GAP-NNN has a research doc, a detector, and tests
python3 scripts/audit_gap_test_counts.py   # recompute AUDIT.md's "Tests" column
```

`doctor.py` is part of CI (the `lint` job): if the registry drifts from
the files on disk (say, someone added a gap to `gap_registry.py` but
forgot the detector or the test), the build fails right away instead of
staying unnoticed until the next manual audit. A separate check verifies
that the detector file tree in `ARCHITECTURE.md` hasn't drifted from the
actual file list in `ora2pg_gap_report/detectors/` (exactly the class of
problem that once left the README with a stale architecture description
for a while) — also part of `doctor.py`, not just the registry checks.

## Testing

```sh
pip install -e ".[dev]"   # editable install + pytest/ruff/mypy
pytest
ruff check ora2pg_gap_report/ tests/
mypy                       # ora2pg_gap_report/ + scripts/, config in pyproject.toml
```

`mypy` is configured with `disallow_untyped_defs` — not just "doesn't
fail on annotated code," it actually requires an annotation on every
function. `oracledb` (the optional `oracle` extra's dependency) is marked
`ignore_missing_imports` — its types are only used under `if
TYPE_CHECKING:` (`oracle_connector.py`), so the package stays importable
without it, and `mypy` doesn't fail in CI, where `oracledb` isn't
installed.

The detectors and the lexer are checked against real open-source PL/SQL
code, not just synthetic examples. Beyond targeted fixtures (Logger, a
compound trigger from Apress), the detectors were also run in full
against 247,298 lines (an exact, current count via `git clone --depth 1`
of each repository) from seven independent open-source projects:
Oracle's own demo schemas (`oracle-samples/db-sample-schemas`), the
`mortenbra/alexandria-plsql-utils` utility library, the
`utPLSQL/utPLSQL` unit-testing framework, the `OraOpenSource/Logger`
logger, the `method5/plsql_lexer` lexer/tokenizer, the `mbleron/ExcelGen`
Excel-file generator, and the `osalvador/tePLSQL` templating engine —
zero crashes, only one honestly documented boundary of applicability (see
`test_real_open_source_logger_install_script_
anonymous_block_is_unknown_not_a_crash` in `tests/test_bulk_collect.py`).
Details and the full list of corpus-validated detectors are in
`research/AUDIT.md`.

### Checking against a live Oracle

`oracle_connector.py`'s unit tests run against a fake connection
(`tests/fakes/fake_oracle.py`) — fast, deterministic, no Oracle required.
The live path ("connect to a real Oracle → export via
`DBMS_METADATA.GET_DDL` → analyze") isn't covered by those, it needs a
real database:

```sh
docker compose -f scripts/oracle-test-compose.yml up -d
docker compose -f scripts/oracle-test-compose.yml logs -f   # wait for "DATABASE IS READY TO USE"

pip install -e ".[oracle]"
ORACLE_DSN=localhost:1521/FREEPDB1 ORACLE_USER=testuser ORACLE_PASSWORD=testpass1 \
  python scripts/verify_against_live_oracle.py
```

The script creates a couple of scaffolding tables
(`scripts/setup_oracle_test_schema.sql` — unlike packages, triggers need
an actually-existing target table), loads the real fixtures from
`docs/research/samples/` as-is, exports them back out via a live
`DBMS_METADATA.GET_DDL`, runs the detectors, and cross-checks the counts
against what was already independently verified against the same files
as plain text (`tests/`). If `ora2pg` is on `PATH`, it also runs
`SHOW_REPORT` against the live connection.

`gvenzl/oracle-free:23-slim` is a container packaging of the official
free Oracle distribution (the same engine), just with a wrapper that's
more convenient for CI/tests than the raw Oracle Container Registry
image.
