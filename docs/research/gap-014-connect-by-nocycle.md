# GAP-014: `CONNECT BY NOCYCLE` / `ORDER SIBLINGS BY` — структурное разрушение блока при конвертации

Oracle feature: расширения иерархических запросов сверх базового
`CONNECT BY` (см. GAP-005 про сам `CONNECT BY` и известный баг с
`LEVEL`) — `NOCYCLE` (защита от циклов в графе) и `ORDER SIBLINGS BY`
(сортировка потомков внутри одного родителя, сохраняющая иерархический
порядок обхода).

## Минимальный пример

```sql
CREATE OR REPLACE PROCEDURE build_tree AS
BEGIN
    FOR r IN (
        SELECT employee_id
        FROM employees
        START WITH manager_id IS NULL
        CONNECT BY NOCYCLE PRIOR employee_id = manager_id
        ORDER SIBLINGS BY employee_id
    ) LOOP
        NULL;
    END LOOP;
END;
/
```

## Вывод ora2pg (v25.0, `-t PACKAGE`)

В отличие от обычного `CONNECT BY` (переводится в `WITH RECURSIVE` внутри
тела функции, с известным отдельным багом про `LEVEL` — см. GAP-005), это
расширение ломает конвертацию гораздо серьёзнее: сгенерированный
`WITH RECURSIVE` оказался вставлен **до** `DECLARE`, а тело процедуры
получило нарушенную вложенность `DECLARE`/`CURSOR` — структура всего
блока разваливается, а не только сам иерархический запрос.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16: `CREATE PROCEDURE` падает уже на
этапе компиляции тела функции (синтаксическая ошибка), а не только при
первом вызове — то есть даже раньше, чем для типичных gap'ов в этом
реестре, где `check_function_bodies = false` обычно откладывает ошибку до
первого `CALL`.

Это не просто неточный перевод одной конструкции — это структурное
повреждение всего окружающего PL/SQL-блока, что делает откат/починку
сложнее, чем для точечных gap'ов.

Отдельно проверено: обычный `CONNECT BY` без `NOCYCLE` и без
`ORDER SIBLINGS BY` этим детектором не флагуется — для него уже есть
отдельный, менее серьёзный gap (GAP-005 / `detectors/connect_by.py`).

**Reproducible: YES.** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/connect_by_nocycle.py`. Флагует `CONNECT BY
NOCYCLE` и `ORDER SIBLINGS BY` раздельно (запрос может содержать любую из
двух конструкций, либо обе сразу).
