# GAP-004: `COMPOUND TRIGGER` — a silent file-parser failure

Oracle feature: `COMPOUND TRIGGER` — a trigger with four named sections
(`BEFORE STATEMENT`/`BEFORE EACH ROW`/`AFTER EACH ROW`/`AFTER STATEMENT`)
instead of a single `BEGIN...END` body.

## What is actually wrong here

The project's strongest and most unambiguously confirmed finding — and the
only one where a real run produced a binary "not found" result rather than
"found, but inaccurate".

On a real file containing a syntactically correct `COMPOUND TRIGGER`
(`Apress/modern-oracle-database-programming`, `tr_constructors_cti`, all
four sections):

```
ora2pg -t TRIGGER -i compound_trigger_apress.sql --estimate_cost ...
[...] 0/0 triggers (100.0%) end of output.
-- Nothing found of type TRIGGER
```

The control run in the same session, on a classic simple trigger (`BEFORE
INSERT OR UPDATE ... FOR EACH ROW BEGIN ... END`), reported `1/1 triggers`
and converted correctly. This is not an environment problem — it is a
specific, reproducible parser failure on compound triggers.

**Cause (from the code):** `read_trigger_from_file()` (`Ora2Pg.pm`, around
line 3868) parses a trigger body with two rigid regexes, both of which
require `FOR EACH ROW/STATEMENT` to follow `ON <table>` immediately, then
an optional `WHEN (...)`, and then `BEGIN`/`DECLARE` directly. A
`COMPOUND TRIGGER` has neither `FOR EACH ROW` at the top level (the timing
is given separately inside each of the four sections) nor a single `BEGIN`
right after the declaration. Neither regex accounts for this shape, so the
trigger drops out of the result entirely, without a single warning.

**Caveat (not confirmed by a run, from the code only):** in live mode
(connected to Oracle rather than reading a file) the trigger object itself
will be counted in `SHOW_REPORT`'s `TRIGGER: number/invalid` counter — that
counter comes straight from the `ALL_OBJECTS`/`ALL_TRIGGERS` catalog, not
through the file regex parser. So the object count in `SHOW_REPORT` will
not reveal the problem. Judging by the structure of `export_trigger()`
(`Ora2Pg.pm:5975+`), it is highly likely that live mode also produces
syntactically invalid or silently mangled code for the body — there is no
"this is a compound trigger, handle it differently" check anywhere in the
codebase.

## Observed problem

A `COMPOUND TRIGGER` is not "converted incorrectly" — it disappears from
ora2pg's file mode completely, without a single warning. The "number of
triggers / invalid triggers" metric in `SHOW_REPORT` shows nothing
suspicious at all, because it comes from the Oracle catalog rather than
from an attempted conversion. Exactly the kind of gap that gets discovered
after the fact, once something has already broken in production.

**Reproducible: YES** (file mode). Live mode: from the code, not confirmed
by a live run at the time of this research. Ora2Pg version: 25.0 (commit
`cc2c434f`).

## Verdict

**Gap confirmed**, and more strongly than originally assumed.

Implemented in `ora2pg_gap_report/detectors/compound_triggers.py`.
