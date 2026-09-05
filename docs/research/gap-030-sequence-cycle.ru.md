# GAP-030: `CREATE SEQUENCE ... CYCLE` теряет секцию `CYCLE`

Oracle feature: `CREATE SEQUENCE ... CYCLE` — после достижения
`MAXVALUE` (или `MINVALUE` для убывающей последовательности) `NEXTVAL`
не завершается ошибкой, а начинает счёт заново с `MINVALUE`. Обычная
практика для последовательностей с ограниченным диапазоном значений
(коды состояний, номера слотов, циклические идентификаторы партий).

## Минимальный пример

```sql
CREATE SEQUENCE seq_small
  START WITH 1
  INCREMENT BY 1
  MAXVALUE 3
  CYCLE
  NOCACHE
  ORDER;
```

## Вывод ora2pg (v25.0, `-t SEQUENCE`)

```sql
CREATE SEQUENCE seq_small INCREMENT 1 NO MINVALUE MAXVALUE 3 START 1;
```

Секция `CYCLE` пропадает без следа (`ORDER`/`NOCACHE` тоже не
переносятся, но это RAC-специфичная и производительностная семантика
без аналога и без последствий для корректности — не то же самое, что
`CYCLE`).

## Наблюдаемая проблема

Не синтаксическая ошибка — `CREATE SEQUENCE` выполняется без проблем, и
последовательность нормально работает, пока не будет исчерпан её
диапазон. Подтверждено на реальном PostgreSQL 16:

```sql
SELECT nextval('seq_small'), nextval('seq_small'), nextval('seq_small');
--  1 | 2 | 3

SELECT nextval('seq_small');
-- ERROR:  nextval: reached maximum value of sequence "seq_small" (3)
```

В Oracle тот же четвёртый вызов `NEXTVAL` вернул бы `1` и продолжил
работу бесконечно. После миграции последовательность работает
идентично оригиналу ровно до момента исчерпания диапазона — который
может наступить через месяцы после переноса, в проде, а не на
тестировании. Отказ проявляется как `ERROR` при следующей вставке
(INSERT с DEFAULT nextval(...) или явным вызовом), то есть ровно там,
где приложение ожидало, что последовательность работает так же, как в
Oracle.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/sequence_cycle.py`.
