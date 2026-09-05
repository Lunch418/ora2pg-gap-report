# GAP-009: `CREATE TYPE ... AS OBJECT` / `TYPE BODY` — вне оценки трудозатрат вообще

Oracle feature: объектный тип (`CREATE TYPE name AS OBJECT (атрибуты,
MEMBER-методы)` + отдельно `CREATE TYPE BODY` с реализацией методов) —
Oracle-специфичное ООП поверх SQL.

## Что здесь на самом деле не так

Этот gap отличается от остальных в проекте по характеру. Не "ora2pg тихо
портит код", а "ora2pg вообще не пытается оценить стоимость такого
объекта".

## Минимальный пример

```sql
CREATE OR REPLACE TYPE point_t AS OBJECT (
  x NUMBER,
  y NUMBER,
  MEMBER FUNCTION distance_to(p point_t) RETURN NUMBER
);
/
CREATE OR REPLACE TYPE BODY point_t AS
  MEMBER FUNCTION distance_to(p point_t) RETURN NUMBER IS
  BEGIN
    RETURN SQRT(POWER(x - p.x, 2) + POWER(y - p.y, 2));
  END distance_to;
END;
/
```

## Вывод ora2pg (v25.0, `-t TYPE`)

Ora2pg честно помечает вывод: `-- Unsupported, please edit to match
PostgreSQL syntax`, и копирует Oracle-синтаксис как есть под этой пометкой.
Это само по себе не находка — это уже явное предупреждение от самого
ora2pg.

Находка в другом: прогон `ora2pg -t TYPE -i ... --estimate_cost` **не
возвращает вообще ничего** — ни строки отчёта, ни цифры стоимости. У
`--estimate_cost` (судя по коду и по прямому прогону) нет механизма
оценки для объектов типа `TYPE` вообще — он рассчитан только на
`PACKAGE`/`TRIGGER`/`FUNCTION`/`PROCEDURE`.

## Наблюдаемая проблема

Схема с существенным использованием объектных Oracle-типов (что типично
для более старых, ООП-ориентированных enterprise-кодовых баз) получит
**нулевой** вклад в оценку трудозатрат от `--estimate_cost`/`SHOW_REPORT`
за эти объекты — не заниженную оценку, а полное отсутствие какой-либо
цифры. При этом сама миграция объектных типов с методами — одна из самых
трудоёмких задач в принципе: у PostgreSQL нет объектных типов с
методами, только composite types (структуры данных без поведения) —
переписывание требует архитектурного решения (`composite type` +
отдельные функции, вызываемые explicit, а не через `obj.method()`), не
просто синтаксической замены.

**Reproducible: YES** (по коду и по прогону `--estimate_cost`, вернувшему
пустой результат). Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён**, но не в духе "ora2pg врёт", а в духе "ora2pg молчит
там, где стоило бы предупредить громче всего". Реализовано:
`ora2pg_gap_report/detectors/object_type.py`.
