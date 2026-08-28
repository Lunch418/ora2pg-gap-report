# GAP-067: `SDO_GEOMETRY` без `CREATE EXTENSION postgis`

Oracle feature: `SDO_GEOMETRY` — пространственный тип Oracle Spatial.

## Минимальный пример

```sql
CREATE TABLE places (
    id  NUMBER PRIMARY KEY,
    geo MDSYS.SDO_GEOMETRY
);
```

## Вывод ora2pg (v25.0, `-t TABLE`)

```sql
CREATE TABLE places (
	id bigint,
	geo geometry(GEOMETRY)
) ;
ALTER TABLE places ADD PRIMARY KEY (id);
```

Выбор целевого типа правильный: `geometry` — это тип PostGIS,
ближайший аналог `SDO_GEOMETRY`. Но строки `CREATE EXTENSION postgis` в
выводе нет.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16 без предварительно
установленного PostGIS:

```
ERROR:  type "geometry" does not exist
LINE 3:  geo geometry(GEOMETRY)
             ^
```

Отдельно стоит сравнить с поведением того же ora2pg для `SYS_GUID()` в
том же прогоне — там нужное расширение он подключает сам:

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE TABLE tokens (
	id uuid DEFAULT uuid_generate_v4(),
	tag varchar(30)
) ;
```

То есть механизм «вывести CREATE EXTENSION» у ora2pg есть, и для
PostGIS он просто не применяется. Рассчитывать на автоматическое
подключение нужного расширения нельзя.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён, severity medium.** Реализовано:
`ora2pg_gap_report/detectors/sdo_geometry.py`. Severity здесь ниже, чем
у остальных gap'ов этой партии, осознанно: само отображение типа выбрано
верно, и чинится всё одной строкой `CREATE EXTENSION postgis` перед
загрузкой схемы — переписывать конструкцию, в отличие от прочих, не
нужно. Отдельно стоит проверить перенос самих значений: модель координат
и семантика `SDO_GEOMETRY` и PostGIS совпадают не полностью.
