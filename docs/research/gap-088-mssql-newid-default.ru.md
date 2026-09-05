# GAP-088: `NEWID()` — `uuid_generate_v4()` без расширения

MSSQL feature: `NEWID()` / `NEWSEQUENTIALID()` — генерация GUID по
умолчанию.

## Минимальный пример

```sql
CREATE TABLE tokens (
    id uniqueidentifier NOT NULL DEFAULT NEWID(),
    label varchar(50) NULL
);
```

## Вывод ora2pg (v25.0, `-M -t TABLE`)

```sql
CREATE TABLE tokens (
	id uuid NOT NULL DEFAULT uuid_generate_v4(),
	label citext
) ;
```

Цель выбрана правильно — `uuid` и `uuid_generate_v4()`, — но строки
`CREATE EXTENSION IF NOT EXISTS "uuid-ossp"` в выводе нет.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16:

```
ERROR:  function uuid_generate_v4() does not exist
```

`CREATE TABLE` падает немедленно, при загрузке схемы.

Показательно, что механизм подключения расширений у ora2pg есть и в том
же прогоне работает: под строковые типы он сам выводит первой строкой

```sql
CREATE EXTENSION IF NOT EXISTS citext;
```

То есть дело не в отсутствии механизма, а в том, что для `uuid-ossp` он
не применяется. Родственная ситуация на Oracle-стороне —
GAP-067 (`SDO_GEOMETRY` без `CREATE EXTENSION postgis`).

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Вердикт

**Gap подтверждён, severity high.** Чинится одной строкой
`CREATE EXTENSION IF NOT EXISTS "uuid-ossp"` перед загрузкой схемы; в
PostgreSQL 13+ можно вместо этого перейти на встроенную
`gen_random_uuid()` и обойтись без расширения вовсе. Severity здесь
high, а не medium (как у GAP-067), потому что в отличие от PostGIS это
не «доустановить внешнее расширение под особый тип данных», а
блокировка загрузки на совершенно рядовом столбце-идентификаторе.
Реализовано: `ora2pg_gap_report/detectors/mssql_newid_default.py`.
