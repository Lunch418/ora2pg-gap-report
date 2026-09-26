# GAP-003: `BULK COLLECT` / `FORALL` / локальные объявления вложенной таблицы `TYPE`

Oracle feature: массовые операции — `TYPE ... IS TABLE OF ...%TYPE`
(локально объявленный тип коллекции: вложенная таблица или
ассоциативный массив), `BULK COLLECT INTO`, `FORALL` и обращение к
элементам коллекции (`v_ids(i)`, `v_ids.COUNT`). Крайне распространено в
реальном PL/SQL Oracle — это стандартная идиома массовой выборки и DML,
встречающаяся гораздо чаще любой из четырёх целей, которые были у
детекторов проекта до неё.

## Минимальный пример

```sql
CREATE OR REPLACE PACKAGE BODY bulk_test_pkg AS
  PROCEDURE archive_old_orders IS
    TYPE t_id_tab IS TABLE OF orders.order_id%TYPE;
    v_ids t_id_tab;
  BEGIN
    SELECT order_id
    BULK COLLECT INTO v_ids
    FROM orders
    WHERE status = 'CLOSED';

    FORALL i IN 1 .. v_ids.COUNT
      DELETE FROM orders WHERE order_id = v_ids(i);

    COMMIT;
  END archive_old_orders;
END bulk_test_pkg;
/
```

## Вывод ora2pg (v25.0, `-t PACKAGE`)

По сути не сконвертировано: синтаксис Oracle перенесён как есть, с одним
косметическим изменением (`BULK COLLECT INTO` → `BULK COLLECT INTO STRICT`,
что не исправление: `STRICT` — модификатор `SELECT INTO` в PL/pgSQL, никак
не связанный с `BULK COLLECT`). `TYPE t_id_tab IS TABLE OF ...%TYPE`,
`FORALL` и `v_ids.COUNT`/`v_ids(i)` остаются ровно такими, как их написал
Oracle, — ничто из этого не является синтаксисом PL/pgSQL.

## Наблюдаемая проблема

Подтверждено на настоящем сервере PostgreSQL 16. В отличие от GAP-002,
падает сразу — не на каком-то дальнейшем операторе, а на самом объявлении
типа коллекции, ещё до того, как тело функции хоть что-то сделает:

```
ERROR:  syntax error at or near "IS"
LINE 4:     TYPE t_id_tab IS TABLE OF orders.order_id%TYPE;
                          ^
CONTEXT:  invalid type name "t_id_tab IS TABLE OF orders.order_id%TYPE"
```

То же поведение «молча при создании, падает только при первом `CALL`»,
что и у GAP-002 (`check_function_bodies = false` в выводе ora2pg).

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0. Версия PostgreSQL: 16.

## Вердикт

**Gap подтверждён, и серьёзный.** Это не узкий крайний случай, как
GAP-002: `BULK COLLECT`/`FORALL` — одна из самых распространённых идиом
производительности PL/SQL Oracle, она есть практически в любом коде с
пакетной обработкой. Совершенно не сконвертированное локальное объявление
`TYPE` означает, что подпрограмма не пройдёт даже свою секцию `DECLARE`.

По практическому эффекту это, вероятно, самый сильный детектор проекта —
сильнее любого из четырёх, существовавших до него.

Реализован детектор: `ora2pg_gap_report/detectors/bulk_collect.py` —
детектор по исходнику, распознающий `TYPE ... IS TABLE OF` / `BULK COLLECT
INTO` / `FORALL` с помощью инфраструктуры маскирования `plsql_lex.py`,
учитывающий строки и комментарии и проверенный на реальных открытых
примерах (не только на этом синтетическом: подтверждён вживую на
локальном типе коллекции в `docs/research/samples/logger.pkb` и на обоих
примерах составных триггеров).
