# GAP-061: `SUBTYPE ... RANGE` → `CREATE DOMAIN ... RANGE`

Oracle feature: подтип PL/SQL с ограничением диапазона значений.

## Минимальный пример

```sql
CREATE OR REPLACE PACKAGE types_pkg IS
  SUBTYPE small_int IS PLS_INTEGER RANGE 1 .. 100;
  SUBTYPE short_name IS VARCHAR2(30) NOT NULL;
END types_pkg;
/
```

## Вывод ora2pg (v25.0, `-t PACKAGE`)

```sql
-- Oracle package 'types_pkg' declaration, please edit to match PostgreSQL syntax.
CREATE DOMAIN types_pkg.small_int AS integer RANGE 1 .. 100;
CREATE DOMAIN types_pkg.short_name AS varchar(30) NOT NULL;
-- End of Oracle package 'types_pkg' declaration
```

Перевод в `CREATE DOMAIN` сам по себе верный, но оговорка `RANGE`
перенесена дословно.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16:

```
ERROR:  syntax error at or near "RANGE"
LINE 1: CREATE DOMAIN types_pkg.small_int AS integer RANGE 1 .. 100;
                                                     ^
```

Второй подтип из того же примера (`SUBTYPE short_name IS VARCHAR2(30)
NOT NULL`) конвертируется в корректный `CREATE DOMAIN ... NOT NULL` и
загрузился бы без вопросов — падает именно вариант с `RANGE`. Поэтому
детектор помечает только его, а ненагруженные подтипы (и вариант с
`NOT NULL`) намеренно не трогает.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/subtype_range.py`. Ручная переработка:
идея переносится один в один, но другим синтаксисом — через проверку:
`CREATE DOMAIN small_int AS integer CHECK (VALUE BETWEEN 1 AND 100)`.
