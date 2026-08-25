*English | [Русский](CONTRIBUTING.ru.md)*

# Contributing

## Send a finding without any code

You don't have to write a detector yourself. If you have a real Oracle
schema with a construct that `ora2pg` converts with a loss of semantics or
a bug, describe it in [issue #2](https://github.com/Lunch418/ora2pg-gap-report/issues/2)
or open a separate issue: a minimal DDL/PL-SQL example, what `ora2pg`
actually does with it (real output, not what the docs say), and what
happens when you load the result into PostgreSQL.

## Send code

The full process — how a detector gets added, what real-code corpus is
used to check for false positives, how to confirm a finding against a live
Oracle — is described in [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md). In
short:

1. The hypothesis is confirmed in practice: minimal example → real
   `ora2pg` → check the generated PostgreSQL code. If `ora2pg` handled it
   fine, there's no detector to add, that's a normal outcome.
2. Before a PR: `pytest`, `ruff check`, `mypy`, `python3 scripts/doctor.py`
   all green (`doctor.py` is part of CI, catches the registry/docs
   drifting from the code on disk).
3. Every detector gets at least one positive test and at least one guard
   test against false positives.

## Style

No external dependencies in `ora2pg_gap_report/` (other than `rich`, used
only by the CLI wrapper, and `textual`, used only by `tui_app.py`/`--tui`,
an optional `[tui]` extra, not part of the base install). Comments only
where they explain a non-obvious decision ("why", not "what the code
does").
