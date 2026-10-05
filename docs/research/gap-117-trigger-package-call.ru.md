# GAP-117: вызов процедуры пакета из триггера копируется без `CALL`

Oracle feature: тело триггера вызывает процедуру пакета как команду -
`audit_pkg.log_change(:NEW.id, 'X');`, `audit_pkg.touch;`, - так большинство
настоящих триггеров и передают работу дальше.

## Как нашли

`--load-check` на выводе ora2pg для
`docs/research/samples/compound_trigger_dlee.sql`: функции триггеров,
вызывающие `equitable_salaries_pkg.make_equitable`, не загрузились.

## Минимальный пример

```sql
CREATE OR REPLACE TRIGGER t_biu BEFORE INSERT OR UPDATE ON orders FOR EACH ROW
DECLARE
  v NUMBER;
BEGIN
  audit_pkg.log_change(:NEW.id, 'X');
  audit_pkg.touch;
  v := audit_pkg.next_seq(:NEW.id);
  :NEW.total := v;
END;
/
```

Oracle 23ai компилирует и выполняет его (при наличии `audit_pkg`).

## Вывод ora2pg (v25.0, `-t TRIGGER`)

```sql
CREATE OR REPLACE FUNCTION trigger_fct_t_biu() RETURNS trigger AS $BODY$
DECLARE
  v bigint;
BEGIN
  audit_pkg.log_change(NEW.id, 'X');
  audit_pkg.touch;
  v := audit_pkg.next_seq(NEW.id);
  NEW.total := v;
RETURN NEW;
END
$BODY$
 LANGUAGE 'plpgsql';
```

Оба вызова процедур скопированы как есть. Вызов функции внутри
присваивания в порядке.

Внутри пакета такой же вызов конвертируется: в одном прогоне с обоими
пакетами `other_pkg.do_it;` становится `CALL other_pkg.do_it();`, какой бы
пакет ни шёл в файле первым. ora2pg знает, что имя - процедура, только
когда процедура есть в том же прогоне, а триггеры всегда конвертируются
отдельным прогоном (`-t TRIGGER`).

## Наблюдаемая проблема

PostgreSQL 16 отвергает функцию триггера, а затем и сам триггер:

```
ERROR:  42601: syntax error at or near "audit_pkg"
ERROR:  42883: function trigger_fct_t_biu() does not exist
```

**Воспроизводится: ДА.** Ora2Pg 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage deployment.** Допишите
`CALL` перед каждым вызовом процедуры пакета в функции триггера. Вызовы
`DBMS_*`/`UTL_*` оставлены `dbms_utl_calls`.

Реализовано: `ora2pg_gap_report/detectors/trigger_package_call.py`.
