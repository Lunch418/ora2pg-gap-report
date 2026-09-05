# GAP-015: `CREATE CONTEXT` — application context is not converted at all

Oracle feature: `CREATE CONTEXT` declares an application context, often the
basis of VPD/row-level security via `SYS_CONTEXT` together with
`DBMS_SESSION.SET_CONTEXT`.

## Minimal example

```sql
CREATE CONTEXT hr_ctx USING hr.set_ctx_pkg;
```

## ora2pg output (v25.0, `-t TABLE` / full schema export)

The construct disappears from the output completely — no error, no warning
at the ordinary log level. The only trace is a **DEBUG**-level line
("unhandled line") that is easy to miss during a real migration, since the
normal log level does not show it.

## Observed problem

PostgreSQL has no direct analogue of an application context. Whatever used
that context on Oracle — usually `SYS_CONTEXT('hr_ctx', ...)` in VPD
policies or in query predicates — simply loses its data source on
migration, with no signal at all that part of the security configuration
was never carried over. For a VPD scenario that is a potentially serious
silent hole: a policy may either not fire at all, or fire against
empty/default values.

The nearest manual migration paths are `current_setting()`/`set_config()`
for general-purpose session variables, or Row-Level Security (`CREATE
POLICY`) for the VPD scenario specifically.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/context_object.py`.
