# GAP-010: `WITH FUNCTION`/`WITH PROCEDURE` — парсер ora2pg разваливает структуру

Oracle feature (12c+): встроенное определение функции/процедуры прямо
внутри `WITH`-предложения запроса — область видимости ограничена этим
запросом, без отдельного объявления в пакете.

## Минимальный пример

```sql
CREATE OR REPLACE PACKAGE BODY calc_pkg AS
  PROCEDURE run_calc IS
    v_total NUMBER;
  BEGIN
    WITH
      FUNCTION apply_discount(p_amount NUMBER) RETURN NUMBER IS
      BEGIN
        RETURN p_amount * 0.9;
      END;
    SELECT SUM(apply_discount(amount)) INTO v_total FROM orders;
  END run_calc;
END calc_pkg;
/
```

## Вывод ora2pg (v25.0, `-t PACKAGE`)

Это самая серьёзная по характеру находка проекта — не "конструкция не
конвертируется", а **парсер полностью разваливает структуру исходника**:

```sql
CREATE OR REPLACE PROCEDURE calc_pkg_run_calc () AS $body$
DECLARE
    v_total bigint;
BEGIN
    WITH;
$body$
LANGUAGE PLPGSQL
;

CREATE OR REPLACE FUNCTION calc_pkg_apply_discount (p_amount bigint) RETURNS bigint AS $body$
BEGIN
        RETURN p_amount * 0.9;
      END;
    SELECT SUM(calc_pkg_apply_discount(amount)) INTO STRICT v_total FROM orders;
  END;
$body$
LANGUAGE PLPGSQL
;
```

Вложенная `apply_discount` "утекла" наружу как отдельная функция пакета
верхнего уровня (`calc_pkg_apply_discount`), а тело `run_calc` обрезано
буквально до `BEGIN WITH;` — весь реальный запрос (`SELECT SUM(...) INTO
v_total FROM orders`) физически пропал из тела `run_calc` и оказался
приклеен к концу тела `apply_discount` вместо этого.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16: обе `CREATE` проходят без ошибки
(`check_function_bodies = false`), но `run_calc` падает уже на этапе
**компиляции** тела функции при первом вызове (не просто выполнения):

```
ERROR:  syntax error at end of input
CONTEXT:  compilation of PL/pgSQL function "calc_pkg_run_calc" near line 7
```

**Reproducible: YES.** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён, и это структурная порча кода, а не просто
неконвертированная конструкция.** Реализовано:
`ora2pg_gap_report/detectors/with_function.py`.
