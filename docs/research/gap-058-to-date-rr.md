# GAP-058: the `RR` format in `TO_DATE` — silently wrong dates

Oracle feature: `RR` — a two-digit year code with a pivot rule: 00-49 is
read as 20xx, 50-99 as 19xx.

## Minimal example

```sql
SELECT TO_DATE('85-06-01', 'RR-MM-DD') AS d1,
       TO_DATE('15-06-01', 'RR-MM-DD') AS d2
  FROM dual;
```

On Oracle these are 1985-06-01 and 2015-06-01.

## ora2pg output (v25.0, `-t QUERY`)

```sql
SELECT to_date('85-06-01','RR-MM-DD') AS d1,
       to_date('15-06-01','RR-MM-DD') AS d2;
```

`RR` is left in the format string as written.

## Observed problem

There is no error at all — neither at load nor at execution. The query
runs and returns a result. Confirmed against a real PostgreSQL 16:

```
      d1       |      d2
---------------+---------------
 0001-06-01 BC | 0001-06-01 BC
(1 row)
```

Both dates are year 1 **BC**, instead of 1985 and 2015. PostgreSQL does
not know the `RR` code and does not complain about it. `RRRR` was checked
too — the same result (`0001-06-01 BC`), so the detector flags both codes.

Worth noting separately is an asymmetry in ora2pg itself. In `TO_CHAR` it
does replace `RR` with `YY`:

```sql
SELECT TO_CHAR(hired, 'RR') AS rr_year FROM employees;
```
```sql
SELECT TO_CHAR(hired, 'YY') AS rr_year FROM employees;
```

but in `TO_DATE` it does not. For `TO_CHAR`, incidentally, the replacement
is harmless: on output `RR` and `YY` produce the same thing, since the
pivot rule applies only when parsing an input string. So ora2pg
substitutes where it is not needed and does not substitute where it is.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Verdict

**Gap confirmed.** Implemented in
`ora2pg_gap_report/detectors/to_date_rr.py`. This is one of the two
detectors working over `mask_comments_only()`: the text being searched for
is the format string itself, and ordinary literal masking would erase it.

Manual rework: replace `RR` with an explicit four-digit `YYYY` and adjust
the input data accordingly.

**`YY` is not an equivalent here**, though at first glance it looks like
one — and this is worth checking separately, because the error is silent.
The two rules have different thresholds. Confirmed against a real
PostgreSQL 16:

```sql
SELECT to_date('49-06-01','YY-MM-DD') AS yy49,
       to_date('50-06-01','YY-MM-DD') AS yy50,
       to_date('69-06-01','YY-MM-DD') AS yy69,
       to_date('70-06-01','YY-MM-DD') AS yy70,
       to_date('85-06-01','YY-MM-DD') AS yy85;
```
```
    yy49    |    yy50    |    yy69    |    yy70    |    yy85
------------+------------+------------+------------+------------
 2049-06-01 | 2050-06-01 | 2069-06-01 | 1970-06-01 | 1985-06-01
```

| Range | Oracle `RR` | PostgreSQL `YY` | Match |
|---|---|---|---|
| 00-49 | 20xx | 20xx | yes |
| 50-69 | **19xx** | **20xx** | **no — exactly 100 years apart** |
| 70-99 | 19xx | 19xx | yes |

So `'65'` is 1965 under Oracle's `RR` and 2065 under PostgreSQL's `YY`. A
mechanical `RR` → `YY` substitution fixes the loud breakage (year 1 BC)
and replaces it with a quiet one, on a subset of the data. For dates of
birth, historical records, and any mid-twentieth-century data, that is
exactly the range that diverges.

Because no error is raised in either the original or the "fixed" variant,
this gap is especially dangerous: the divergence surfaces only as wrong
data.
