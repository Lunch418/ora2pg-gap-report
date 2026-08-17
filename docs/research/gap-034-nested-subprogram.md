# GAP-034: Локальная вложенная процедура/функция теряет структуру при экспорте

Oracle feature: локально объявленная процедура/функция внутри
декларативной секции другого блока (пакета, процедуры, функции,
анонимного блока) — до `BEGIN` содержащего блока. Обычный способ
вынести вспомогательную логику, нужную только внутри одной процедуры,
не делая её отдельным членом пакета.

## Минимальный пример

```sql
CREATE OR REPLACE PROCEDURE outer_proc AS
  PROCEDURE inner_proc(p_val NUMBER) IS
  BEGIN
    DBMS_OUTPUT.PUT_LINE('inner: ' || p_val);
  END;
BEGIN
  inner_proc(42);
END;
```

## Вывод ora2pg (v25.0, `-t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE inner_proc (p_val bigint) AS $body$
BEGIN
    RAISE NOTICE 'inner: %', p_val;
  END;
BEGIN
  CALL inner_proc(42);
END;
$body$
LANGUAGE PLPGSQL
;
```

Вложенная `inner_proc` "утекает" наружу как отдельная процедура верхнего
уровня — `outer_proc` в выводе не существует вообще. Хуже того, тело
`inner_proc` в выводе искажено: после её собственного `END;` без точки с
запятой обрыва идёт `BEGIN CALL inner_proc(42); END;` того, что должно
было быть исполняемым телом `outer_proc` — всё это оказывается
приклеено внутрь тела `inner_proc` как один блок.

## Наблюдаемая проблема

`CREATE PROCEDURE` в выводе выполняется без единой ошибки — ora2pg
отключает `check_function_bodies` в самом начале сгенерированного
файла, так что синтаксис тела не проверяется на этапе `CREATE`. Отказ
происходит только при первом реальном вызове, на этапе компиляции тела:

```sql
CALL inner_proc(1);
-- ERROR:  syntax error at or near "BEGIN"
-- LINE 5: BEGIN
-- CONTEXT:  compilation of PL/pgSQL function "inner_proc" near line 2
```

Ровно тот же паттерн, что и у `$IF`/`$THEN` (GAP-035): скрипт миграции
успешно "накатывается" целиком, все объекты вроде бы созданы, а сломанный
код обнаруживается только когда до него реально доходит вызов — что
может случиться не на тестировании, а в проде. Плюс исходная процедура
(`outer_proc`) вообще пропадает из вывода без предупреждения — теряется
не только вложенная функция, но и то, что её вызывало.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/nested_subprogram.py`.
