# GAP-027: `CREATE MATERIALIZED VIEW LOG` не конвертируется вообще

Oracle feature: журнал изменений таблицы (`CREATE MATERIALIZED VIEW LOG
ON table ...`), нужный для инкрементального `FAST REFRESH`
материализованных представлений, построенных на этой таблице.

## Минимальный пример

```sql
CREATE TABLE products (
    product_id NUMBER,
    name       VARCHAR2(100)
);

CREATE MATERIALIZED VIEW LOG ON products
WITH ROWID, SEQUENCE (product_id, name)
INCLUDING NEW VALUES;
```

## Вывод ora2pg (v25.0, `-t TABLE`)

```
[DEBUG] unhandled line: CREATE MATERIALIZED VIEW LOG ON products
WITH ROWID, SEQUENCE (product_id, name)
INCLUDING NEW VALUES;
```

Конструкция полностью пропадает из вывода — не как
`-- Unsupported`-комментарий, а без единого следа кроме служебной строки
уровня **DEBUG** в логе.

## Наблюдаемая проблема

Не синтаксическая ошибка — сама таблица `products` создаётся
нормально, журнал просто не появляется вообще. Если где-то в схеме
построено материализованное представление с `REFRESH FAST` на этой
таблице, оно перестаёт работать в режиме быстрого обновления без явного
журнала. В PostgreSQL у материализованных представлений нет
инкрементального `REFRESH FAST` вообще — только полный `REFRESH
MATERIALIZED VIEW` — так что сама концепция журнала изменений там не
нужна, но это означает архитектурно другой подход к освежению данных
(полный пересчёт вместо инкрементального), который нужно спроектировать
заново, а не просто перенести синтаксис.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/materialized_view_log.py`. Severity
`high` — тот же профиль, что у GAP-013/GAP-018
(`table_partitioning`/`external_table`): конструкция молча пропадает
без единой ошибки от PostgreSQL, но означает реальную архитектурную
потерю (здесь — стратегия обновления зависимых материализованных
представлений), а не просто субоптимальность (ср. GAP-025, где
severity `medium` именно потому, что риск ограничен планом выполнения).
