# GAP-001: `PRAGMA AUTONOMOUS_TRANSACTION` — cost underestimated in a package body

Oracle feature: `PRAGMA AUTONOMOUS_TRANSACTION` marks a procedure or
function as running in a separate, independent transaction.

## What is actually wrong here

This is the project's most counterintuitive finding: **ora2pg really does
convert** this pragma — it is not a case of "doesn't carry it over". By
default it generates a dblink wrapper: the function is renamed to
`<name>_atx`, the `COMMIT` inside it is removed, and the calling code gets
a proxy function that invokes `<name>_atx` through `dblink()` on a
separate connection. Confirmed by a live run on `logger.pkb` — a working
dblink wrapper really does appear in the output for every procedure
carrying `pragma autonomous_transaction;`.

The problem is not the conversion, it is the **cost estimate**. ora2pg's
`%UNCOVERED_SCORE` contains the weight `'PRAGMA' => 3`, which is supposed
to be added when `PRAGMA AUTONOMOUS_TRANSACTION` is seen. But for
functions **inside a package body** the cost is computed only from the
text **after** `BEGIN` (`Ora2Pg/Oracle.pm::_lookup_function`,
`split(/\bBEGIN\b/i, $plsql, 2)`), while `PRAGMA AUTONOMOUS_TRANSACTION;`
syntactically always sits in the declarative section — **before** `BEGIN`.
For package functions that part of the text is simply never handed to
`estimate_cost`.

Confirmed empirically: in the real conversion output for `logger.pkb`, the
final cost estimate for `logger.save_global_context` — a function for
which ora2pg itself generated a dblink wrapper, so it definitely "saw" the
pragma — contains no `PRAGMA` line in its breakdown at all, even though a
weight is defined for it. Of the 9 occurrences of `pragma` in
`logger.pkb`, not one is reflected in the cost in any of the package's
per-function reports. Control check: the same `CONNECT BY` inside a
function body (after `BEGIN`) is counted correctly — confirming the cause
is the construct's position relative to `BEGIN`, not that `PRAGMA` is
never looked for.

## Observed problem

ora2pg genuinely converts the construct, but systematically underestimates
its effort and risk in `SHOW_REPORT` and `--estimate_cost` for package
functions. And "carried over" here means, in practice: the code starts
calling another database through `dblink`, with a connection string to be
configured by hand — a network dependency between procedures that may be
unacceptable in an environment with strict isolation requirements.
`SHOW_REPORT` will at best show an understated number, and at worst show
nothing specific to this construct at all.

**Reproducible: YES.** Ora2Pg version: 25.0 (commit `cc2c434f`).

## Verdict

**Gap confirmed.** Not "isn't carried over", but "is carried over, yet
underestimated, and creates an architectural dependency the cost figure
gives no warning about".

Implemented in `ora2pg_gap_report/detectors/autonomous_tx.py`.

## Why PACKAGE BODY only

Re-measured against ora2pg 25.0 (2026-09-05), four `--estimate_cost` runs
on minimal examples:

| source | with `PRAGMA` | without `PRAGMA` | difference |
|---|---|---|---|
| `PACKAGE BODY` | 6 units | 6 units | **0** |
| standalone `PROCEDURE` | 4.2 units | 4.0 units | 0.2 |

In both cases ora2pg generates the same workaround: `CREATE EXTENSION
dblink`, a connection string to be filled in by hand, and a `dblink()`
call on every invocation. But inside a package body it charges nothing for
it — the estimate matches the same procedure without the `PRAGMA` to the
unit. That is the registered gap.

For a standalone procedure the estimate does go up. 0.2 units is one
minute at the default 5 min/unit, and for "install an extension, configure
a connection string, and accept a network round trip" that is clearly too
little. But "too little" is a judgement and "nothing" is a fact, and by
this project's methodology only a reproduced breakage enters the registry.
So the detector deliberately does not fire on a standalone routine; if
ora2pg ever stops counting there too, that will be a separate gap with its
own reproduction.
