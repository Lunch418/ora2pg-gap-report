# GAP-051: `SYS.ANYDATA` как тип столбца

Oracle feature: `ANYDATA` / `ANYDATASET` / `ANYTYPE` — самоописывающийся
контейнер, хранящий значение любого типа вместе с информацией о самом
типе.

## Минимальный пример

```sql
CREATE TABLE settings (
    id  NUMBER PRIMARY KEY,
    val SYS.ANYDATA
);
```

## Вывод ora2pg (v25.0, `-t TABLE`)

```sql
CREATE TABLE settings (
	id bigint,
	val SYS.ANYDATA
) ;
```

Имя типа перенесено как есть, вместе со схемой `SYS`.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16:

```
ERROR:  schema "sys" does not exist
LINE 3:  val SYS.ANYDATA
             ^
```

Для короткой записи (`ANYDATA` без префикса) ошибка будет про
несуществующий тип. Падает сразу на загрузке DDL.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/anydata_type.py`. Ручная переработка:
механической замены нет — столбец обычно переразмечают в `jsonb` (если
важно хранить произвольную структуру) либо разносят на несколько
типизированных столбцов с признаком типа, если реально хранились
два-три конкретных варианта.
