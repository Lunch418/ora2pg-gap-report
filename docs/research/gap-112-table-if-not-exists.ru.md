# GAP-112: `CREATE TABLE IF NOT EXISTS` Oracle 23ai превращается в таблицу `if`

Oracle feature (23ai и новее): `CREATE TABLE IF NOT EXISTS`.
`DBMS_METADATA.GET_DDL` его никогда не пишет; рукописные скрипты
развёртывания под 23ai — пишут.

## Минимальный пример

```sql
CREATE TABLE IF NOT EXISTS customers (
  id NUMBER PRIMARY KEY,
  name VARCHAR2(50)
);
```

## Вывод ora2pg (v25.0, `-t TABLE`)

```sql
\set ON_ERROR_STOP ON
CREATE TABLE if (
	not EXISTS
) ;
ALTER TABLE if ADD PRIMARY KEY (not);
```

Разбор таблиц берёт слово после `TABLE` за имя таблицы — тот же сбой, что
у MySQL в GAP-110, в том же общем коде.

## Наблюдаемая проблема

```
ERROR:  syntax error at or near "not"
```

при загрузке, и `\set ON_ERROR_STOP ON` останавливает загрузку всей
схемы. A/B: та же таблица без `IF NOT EXISTS` конвертируется и
загружается.

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён, severity high, failure_stage deployment.** Исправляется
до конвертации удалением `IF NOT EXISTS`.

Реализовано: `ora2pg_gap_report/detectors/table_if_not_exists.py`.
