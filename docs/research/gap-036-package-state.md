# GAP-036: Пакетная переменная (состояние на уровне сессии) — сломанная эмуляция через `set_config`

Oracle feature: переменная, объявленная на верхнем уровне `PACKAGE
BODY` (не внутри конкретной процедуры/функции) — состояние, живущее на
протяжении всей сессии, общее для всех процедур пакета. Частый паттерн
— пакет-контекст (`g_user_id`, `g_tenant_id` и подобное), выставляемый
один раз в начале сессии и читаемый много раз внутри разных процедур
того же пакета.

## Минимальный пример

```sql
CREATE OR REPLACE PACKAGE pkg_ctx AS
  g_user_id NUMBER;
  PROCEDURE set_user(p_id NUMBER);
  FUNCTION get_user RETURN NUMBER;
END pkg_ctx;
/
CREATE OR REPLACE PACKAGE BODY pkg_ctx AS
  PROCEDURE set_user(p_id NUMBER) IS
  BEGIN
    g_user_id := p_id;
  END;
  FUNCTION get_user RETURN NUMBER IS
  BEGIN
    RETURN g_user_id;
  END;
END pkg_ctx;
```

## Вывод ora2pg (v25.0, `-t PACKAGE`)

```sql
CREATE OR REPLACE PROCEDURE pkg_ctx_set_user (p_id bigint) AS $body$
BEGIN
    PERFORM set_config('pkg_ctx.g_user_id', p_id, false);
  END;
$body$
LANGUAGE PLPGSQL
;

CREATE OR REPLACE FUNCTION pkg_ctx_get_user () RETURNS bigint AS $body$
BEGIN
    RETURN current_setting('pkg_ctx.g_user_id')::bigint;
  END;
$body$
LANGUAGE PLPGSQL
;
```

Сама идея решения разумная — `set_config()`/`current_setting()` с
пользовательским GUC-параметром (`pkg_ctx.g_user_id`), третий аргумент
`set_config` — `false` (не транзакционно-локально), что действительно
соответствует времени жизни пакетной переменной в Oracle (вся сессия).
Но реализация сломана в двух местах.

## Наблюдаемая проблема

**Первая:** `set_config()` принимает `text` вторым аргументом, а
`p_id` — `bigint`. ora2pg не добавляет явное приведение типа.
Подтверждено на реальном PostgreSQL 16 — падает при самом первом вызове,
без единого исключения:

```sql
CALL pkg_ctx_set_user(42);
-- ERROR:  function set_config(unknown, bigint, boolean) does not exist
-- HINT:  No function matches the given name and argument types.
```

**Вторая (проявится даже после ручного добавления `::text`):**
в Oracle необъявленная (не выставленная явно) числовая пакетная
переменная по умолчанию — `NULL`, чтение до первого `SET` просто вернёт
`NULL`, без ошибки. `current_setting()` на ещё не установленный
пользовательский GUC-параметр в PostgreSQL завершается ошибкой, если не
передать второй аргумент `missing_ok => true`:

```sql
SELECT pkg_ctx_get_user();
-- ERROR:  unrecognized configuration parameter "pkg_ctx.g_user_id"
```

Обе ошибки не синтаксические — `CREATE PROCEDURE`/`CREATE FUNCTION`
проходят без проблем (`check_function_bodies` отключён), падение
происходит только при вызове. Первая ошибка воспроизводится
гарантированно при любом использовании — не пограничный случай. Вторая
зависит от порядка вызовов внутри сессии (нормальный сценарий —
`get_user()` вызывается в сессии, где `set_user()` ещё не был вызван,
что для многих реальных пакетов-контекстов случается регулярно —
например при кэшировании соединений в пуле).

**Reproducible: YES.** Ora2Pg version: 25.0.

## Дополнительно проверено: package-level CONSTANT и объявление в спеке

Первая версия детектора (см. `git log` по `package_state.py`) смотрела
только на объявления в `PACKAGE BODY` и пропускала `CONSTANT`. Оба
случая проверены реальным прогоном ora2pg 25.0 отдельно:

**CONSTANT.** Пакетная константа получает тот же рерайт, что и обычная
переменная — реального отличия в поведении ora2pg нет:

```sql
CREATE OR REPLACE PACKAGE BODY pkg_ctx AS
  c_max_retries CONSTANT PLS_INTEGER := 3;
  FUNCTION get_retries RETURN PLS_INTEGER IS
  BEGIN
    RETURN c_max_retries;
  END;
END pkg_ctx;
```

сгенерированный вывод:

```sql
CREATE OR REPLACE FUNCTION pkg_ctx_get_retries () RETURNS integer AS $body$
BEGIN
    RETURN current_setting('pkg_ctx.c_max_retries')::integer;
  END;
$body$
```

Хуже, чем для обычной переменной: у константы вообще нет
"первого `SET`" — ora2pg не генерирует никакого `set_config()` для её
исходного значения (`:= 3`), так что `current_setting()` гарантированно
упадёт с `unrecognized configuration parameter` при любом обращении, не
только до первого вызова записывающей процедуры.

**Объявление в спеке, не в теле.** `PACKAGE ... AS <var>; ... END;`
(без переобъявления в `PACKAGE BODY`) — тоже полноценно попадает под
рерайт; ora2pg не различает, откуда взялась пакетная переменная.
Детектор изначально смотрел только на `PACKAGE BODY` (собственный
минимальный пример этого документа объявляет переменную в спеке и
поэтому не детектировался вообще — баг, а не отдельный
неподтверждённый случай, найден аудитом кода и исправлен).

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/package_state.py`.
