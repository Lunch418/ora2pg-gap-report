# GAP-037: `ORGANIZATION INDEX` (index-organized table) is dropped

Oracle feature: `CREATE TABLE ... ORGANIZATION INDEX` — an index-organized
table (IOT). The data is stored physically inside the primary key's own
structure rather than in a separate heap referenced from the index. For
tables accessed almost exclusively by primary key (caches, reference data,
dictionary tables) this is a deliberate choice of a specific storage
architecture: there is no separate "index → heap" lookup on every access.

## Minimal example

```sql
CREATE TABLE lookup_cache (
    cache_key   VARCHAR2(64),
    cache_value VARCHAR2(4000),
    CONSTRAINT pk_lookup_cache PRIMARY KEY (cache_key)
) ORGANIZATION INDEX;
```

## ora2pg output (v25.0, `-t TABLE`)

```sql
CREATE TABLE lookup_cache (
	cache_key varchar(64),
	cache_value varchar(4000)
) ;
ALTER TABLE lookup_cache ADD PRIMARY KEY (cache_key);
```

The `ORGANIZATION INDEX` clause disappears without trace. The table is
converted as an ordinary heap with a separate primary-key index — correct
with respect to integrity constraints (`cache_key` uniqueness is still
guaranteed), but not the same storage.

## Observed problem

Neither a syntax error nor data loss — the `CREATE TABLE` and `ALTER TABLE
... ADD PRIMARY KEY` run without trouble on a real PostgreSQL 16, and the
table works correctly. What is lost is an architectural storage property:
an IOT has no separate heap at all — a primary-key access is one traversal
of the index structure, not an index lookup followed by a heap fetch.
PostgreSQL supports declarative partitioning and many index types, but it
has no true index-organized tables (data physically inside the index
structure) — a `PRIMARY KEY` in PostgreSQL always creates a separate index
over a separate heap. For performance-sensitive cache tables originally
designed as IOTs for exactly this property, the silent loss of the storage
architecture is not a functional break, but it is a reason to re-check
performance under real load after migration.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/index_organized_table.py`.
