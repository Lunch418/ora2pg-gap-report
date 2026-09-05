# GAP-105: `ROWVERSION` становится `bytea` и перестаёт обновляться

MSSQL feature: `ROWVERSION` — столбец, значение которого сервер сам
меняет при каждом изменении строки. На нём обычно построена
оптимистичная блокировка.

## Минимальный пример

```sql
CREATE TABLE versioned (
    id int NOT NULL PRIMARY KEY,
    rv rowversion NOT NULL
);
```

## Вывод ora2pg (v25.0, `-M -t TABLE`)

```sql
CREATE TABLE versioned (
	id integer NOT NULL,
	rv bytea NOT NULL
) ;
ALTER TABLE versioned ADD PRIMARY KEY (id);
```

Тип по размеру подходит, но главного — самообновления — у `bytea` нет.

## Наблюдаемая проблема

Ошибки не будет ни на одном этапе, и это самое опасное. После миграции
значение `rv` не меняется никогда, а значит проверка вида

```sql
UPDATE versioned SET ... WHERE id = @id AND rv = @rv_прочитанное;
```

совпадает всегда. Конфликт одновременных правок перестаёт
обнаруживаться, и правки молча затирают друг друга — ровно тот сценарий,
ради предотвращения которого столбец и заводили.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Вердикт

**Gap подтверждён, severity high, failure_stage semantic.**
Восстанавливается триггером `BEFORE UPDATE`, увеличивающим счётчик
версии, либо переходом на `xmin` — системный столбец PostgreSQL, который
меняется при каждом обновлении строки сам. Отдельно проверьте столбцы
типа `timestamp`: в T-SQL это устаревший синоним `ROWVERSION`, и
детектор его намеренно не помечает, чтобы не путать со столбцом, который
просто называется `timestamp`. Реализовано:
`ora2pg_gap_report/detectors/mssql_rowversion.py`.
