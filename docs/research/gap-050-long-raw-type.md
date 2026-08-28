# GAP-050: `LONG RAW` конвертируется в `text`, а не в `bytea`

Oracle feature: `LONG RAW` — унаследованный двоичный тип.

## Минимальный пример

```sql
CREATE TABLE binstuff (
    id       NUMBER PRIMARY KEY,
    a_raw    RAW(200),
    a_long   LONG,
    a_lraw   LONG RAW,
    a_blob   BLOB,
    a_clob   CLOB,
    a_bfile  BFILE
);
```

Все типы взяты в один пример намеренно — чтобы отображение `LONG RAW`
можно было сравнить с соседними в том же самом прогоне.

## Вывод ora2pg (v25.0, `-t TABLE`)

```sql
CREATE TABLE binstuff (
	id bigint,
	a_raw bytea,
	a_long text,
	a_lraw text,
	a_blob bytea,
	a_clob text,
	a_bfile bytea
) ;
```

`RAW(200)`, `BLOB` и `BFILE` отображены в `bytea` правильно. `LONG RAW`
— в `text`.

## Наблюдаемая проблема

Это расхождение ora2pg с собственной документацией, а не сознательный
выбор. Документированное значение по умолчанию (`doc/Ora2Pg.pod`,
директива `DATA_TYPE`) содержит `LONG RAW:bytea`, и то же отображение
прописано в коде — `lib/Ora2Pg/Oracle.pm:45`:

```perl
	'LONG RAW' => 'bytea',
```

`CREATE TABLE` загружается чисто, поэтому на этапе схемы проблема не
видна. Она проявляется на переносе данных: в `text` нельзя положить
произвольные байты. Подтверждено на реальном PostgreSQL 16 —
одни и те же байты в `bytea` и в `text`:

```
 bytea ok | \x00ff01fe
(1 row)

ERROR:  invalid byte sequence for encoding "UTF8": 0x00
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/long_raw_type.py`. Ручная переработка:
поправить тип столбца на `bytea` — то самое отображение, которое ora2pg
для `LONG RAW` и декларирует. Обычный `LONG` (символьный тип)
отображается в `text` корректно и детектором не помечается.
