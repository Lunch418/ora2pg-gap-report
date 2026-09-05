# GAP-047: `CREATE TABLE ... OF <type>` — `OF` becomes a column name

Oracle feature: an object table — every row is an instance of an object
type, and the type's attributes become the columns.

## Minimal example

```sql
CREATE TABLE person_objs OF person_typ (
    person_id PRIMARY KEY
);
```

## ora2pg output (v25.0, `-t TABLE`)

```sql
CREATE TABLE person_objs (
	of PERSON_TYP
) ;
```

The keyword `OF` has ended up in the output as a **column name**, the type
became that column's type, and the `person_id PRIMARY KEY` declaration was
lost entirely.

## Observed problem

The most dangerous part is that when the type exists in the target
database, the load succeeds **without a single error**. Checked against a
real PostgreSQL 16:

```sql
CREATE TYPE person_typ AS (person_id bigint, full_name text);
-- then load the file ora2pg generated:
-- CREATE TABLE
```

The resulting structure:

```
              Table "public.person_objs"
 Column |    Type    | Collation | Nullable | Default
--------+------------+-----------+----------+---------
 of     | person_typ |           |          |
```

The table is created and the migration looks successful — but the
structure is wrong: a single column named `of`, and no primary key. If the
type does not exist in the target database the error is different and more
noticeable (`type "person_typ" does not exist`) — so having the type makes
the problem quieter, not safer.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/object_table.py`. Manual rework: expand the
object table into an ordinary table with one column per type attribute,
plus explicit constraints.
