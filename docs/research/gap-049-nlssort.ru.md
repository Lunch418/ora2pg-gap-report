# GAP-049: `NLSSORT` — сортировка по правилам языка

Oracle feature: `NLSSORT(col, 'NLS_SORT=<язык>')` — ключ сортировки по
правилам конкретного языка.

## Минимальный пример

```sql
SELECT name FROM employees
 ORDER BY NLSSORT(name, 'NLS_SORT=GERMAN');
```

## Вывод ora2pg (v25.0, `-t QUERY`)

```sql
SELECT name FROM employees
 ORDER BY name COLLATE "GERMAN";
```

Замена на `COLLATE` сделана верно по форме, но имя языка Oracle
подставлено как имя collation PostgreSQL один в один.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16 (против реально существующей
таблицы `employees`):

```
ERROR:  collation "GERMAN" for encoding "UTF8" does not exist
LINE 2:  ORDER BY name COLLATE "GERMAN";
                       ^
```

Имена сортировок у Oracle и PostgreSQL не совпадают: `GERMAN`,
`FRENCH`, `RUSSIAN` и прочие Oracle-имена в PostgreSQL не существуют.
Ошибка возникает не на загрузке схемы, а при выполнении запроса.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/nlssort.py`. Ручная переработка:
сопоставить каждое Oracle-имя с реальной локалью PostgreSQL (для
немецкого — `"de-DE-x-icu"` при сборке с ICU или `"de_DE.utf8"` иначе)
и при необходимости создать её через `CREATE COLLATION`.
