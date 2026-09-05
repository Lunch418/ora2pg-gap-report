# GAP-044: `TIMESTAMP WITH LOCAL TIME ZONE` — теряется часовой пояс

Oracle feature: `TIMESTAMP WITH LOCAL TIME ZONE` — момент времени
хранится нормализованным, а при чтении автоматически пересчитывается в
часовой пояс текущей сессии.

## Минимальный пример

```sql
CREATE TABLE durations (
    id      NUMBER PRIMARY KEY,
    span_ym INTERVAL YEAR(4) TO MONTH,
    span_ds INTERVAL DAY(3) TO SECOND(6),
    ts_ltz  TIMESTAMP WITH LOCAL TIME ZONE
);
```

## Вывод ora2pg (v25.0, `-t TABLE`)

```sql
CREATE TABLE durations (
	id bigint,
	span_ym interval,
	span_ds interval,
	ts_ltz timestamp
) ;
```

`TIMESTAMP WITH LOCAL TIME ZONE` → `timestamp`, то есть **без** часового
пояса. Правильной заменой был бы `timestamptz`.

## Наблюдаемая проблема

Ошибки нет ни на одном этапе — таблица создаётся, `INSERT` проходит,
`SELECT` возвращает значение. Проверено на реальном PostgreSQL 16, что
именно теряется:

```sql
SET TIME ZONE 'UTC';
INSERT INTO durations(id, ts_ltz) VALUES (1, TIMESTAMP '2026-01-15 12:00:00');
SET TIME ZONE 'Asia/Tokyo';
SELECT ts_ltz FROM durations WHERE id = 1;
-- 2026-01-15 12:00:00   (то же самое значение)
```

Тип столбца в итоге — `timestamp without time zone`. В Oracle то же
значение в токийской сессии вернулось бы сдвинутым. То есть пересчёт в
часовой пояс сессии — вся суть исходного типа — молча исчезает.

Отдельно замечено (не выделено в отдельный gap): квалификаторы
`INTERVAL YEAR TO MONTH` / `INTERVAL DAY TO SECOND` тоже теряются,
превращаясь в нетипизированный `interval` — ограничение на допустимые
поля интервала при этом снимается.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/local_time_zone.py`. Ручная правка: заменить
тип столбца на `timestamptz` — он делает ровно то же, что Oracle LTZ.
