# Rejected hypotheses

Hypotheses tested under the project's methodology (real `ora2pg` + real
PostgreSQL) and **not confirmed** — ora2pg handles them correctly. They
are documented on equal footing with the confirmed gaps: just because a
construct sounds Oracle-ishly complicated does not mean it fails to port
(see "Methodology" in the README).

The first batch of rejected hypotheses (`CREATE PACKAGE`, and partly
`DBMS_OUTPUT`/`DBMS_LOB`) is in `step0-show-report-baseline.md`, sections
1 and 4. The later ones are here.

## `XMLTABLE`/`XMLQUERY`

Hypothesis: Oracle-specific XML functions in SQL (`XMLTABLE(... PASSING
... COLUMNS ...)`) do not port.

Test: a minimal example with `XMLTABLE`, parsing an XML parameter into
rows for an `INSERT`, run through `ora2pg -t PACKAGE` (v25.0) and loaded
into a real PostgreSQL 16.

Result: **rejected**. PostgreSQL 10+ has a built-in `xmltable()` function
whose syntax is compatible with the basic Oracle usage —
`PASSING`/`COLUMNS`/`PATH` behave identically. The example actually ran
and inserted the data correctly (`SELECT * FROM orders` after the call
showed the right rows). Ora2pg does not even need a special conversion —
the data types (`NUMBER` → `bigint`) are substituted by the same general
logic as everywhere else. More complex XPath expressions and the rarer
`XMLTABLE` options were not tested — the hypothesis is rejected only for
the basic, most common usage.
