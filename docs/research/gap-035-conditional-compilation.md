# GAP-035: Директивы условной компиляции (`$IF`/`$THEN`/`$ELSE`/`$END`) копируются verbatim

Oracle feature: условная компиляция PL/SQL (`$IF <condition> $THEN ...
$ELSIF ... $ELSE ... $END`) — препроцессорные директивы, обрабатываемые
компилятором Oracle до собственно компиляции тела: код внутри
невыбранной ветки не просто пропускается на выполнении, он вообще не
компилируется. Обычное применение — код, зависящий от версии БД
(`$IF DBMS_DB_VERSION.VERSION >= 12 $THEN ...`), или отладочные секции,
управляемые флагом инспекции (`$$flag_name`).

## Минимальный пример

```sql
CREATE OR REPLACE PROCEDURE proc_debug AS
BEGIN
$IF $$debug_mode $THEN
  DBMS_OUTPUT.PUT_LINE('debug on');
$ELSE
  DBMS_OUTPUT.PUT_LINE('debug off');
$END
  NULL;
END;
```

## Вывод ora2pg (v25.0, `-t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE proc_debug () AS $body$
BEGIN
$IF $$debug_mode $THEN
  RAISE NOTICE 'debug on';
$ELSE
  RAISE NOTICE 'debug off';
$END;
END;
$body$
LANGUAGE PLPGSQL
;
```

`DBMS_OUTPUT.PUT_LINE` конвертируется как обычно, но сами директивы
`$IF`/`$THEN`/`$ELSE`/`$END` копируются в вывод буквально, как обычный
текст. PL/pgSQL не имеет препроцессора условной компиляции вообще — это
не валидный синтаксис ни в каком виде.

## Наблюдаемая проблема

`CREATE PROCEDURE` в выводе выполняется без единой ошибки — ora2pg
отключает `check_function_bodies` в самом начале сгенерированного
файла. Отказ происходит только при первом реальном вызове:

```sql
CALL proc_debug();
-- ERROR:  syntax error at or near "$"
-- LINE 3: $IF $$debug_mode $THEN
--         ^
-- CONTEXT:  compilation of PL/pgSQL function "proc_debug" near line 1
```

Тот же паттерн, что и у вложенных подпрограмм (GAP-034): скрипт
миграции успешно "накатывается" целиком, отказ обнаруживается только
когда до кода реально доходит вызов — не на тестировании миграции, а на
проде, при первом обращении к этой конкретной ветке кода (что особенно
вероятно для `$IF`-веток, управляемых редко переключаемыми флагами вроде
режима отладки).

**Reproducible: YES.** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/conditional_compilation.py`.
