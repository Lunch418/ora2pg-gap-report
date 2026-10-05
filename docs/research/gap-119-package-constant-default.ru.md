# GAP-119: константа пакета в умолчании параметра копируется как есть

Oracle feature: параметр подпрограммы, значение которого по умолчанию -
константа или переменная уровня пакета: `p_os IN VARCHAR2 :=
g_os_windows` или с именем пакета, `p_params tab_param DEFAULT
logger.gc_empty_tab_param`.

## Как нашли

`--load-check` на выводе ora2pg для `file_util_pkg` из
alexandria-plsql-utils (`docs/research/samples/file_util_pkg.pks`/`.pkb`):
две функции упали с `column "g_os_windows" does not exist`. В
OraOpenSource Logger форма с именем пакета встречается в одиннадцати
подпрограммах.

## Минимальный пример

```sql
CREATE OR REPLACE PACKAGE file_pkg AS
  g_os_windows CONSTANT VARCHAR2(1) := 'w';
  FUNCTION sep(p_os IN VARCHAR2 := g_os_windows) RETURN VARCHAR2;
END file_pkg;
/
CREATE OR REPLACE PACKAGE BODY file_pkg AS
  FUNCTION sep(p_os IN VARCHAR2 := g_os_windows) RETURN VARCHAR2 IS
  BEGIN
    RETURN CASE WHEN p_os = g_os_windows THEN '\' ELSE '/' END;
  END;
END file_pkg;
/
```

В живом Oracle 23ai пакет компилируется, а `file_pkg.sep` возвращает `\`.

## Вывод ora2pg (v25.0, `-t PACKAGE`, из `DBMS_METADATA.GET_DDL`)

```sql
CREATE OR REPLACE FUNCTION file_pkg.sep (p_os text DEFAULT g_os_windows) RETURNS varchar AS $body$
BEGIN
    RETURN CASE WHEN p_os = current_setting('file_pkg.g_os_windows')::varchar(1) THEN '\' ELSE '/' END;
  END;
$body$
```

В теле константа переписана в `current_setting()` (эмуляция из GAP-036),
в умолчании параметра - нет.

## Наблюдаемая проблема

PostgreSQL 16 отвергает функцию при загрузке:

```
ERROR:  42703: column "g_os_windows" does not exist
```

Форма с именем пакета, `DEFAULT file_pkg.g_os_windows`, тоже падает:

```
ERROR:  42P01: missing FROM-clause entry for table "file_pkg"
```

**Воспроизводится: ДА.** Ora2Pg 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage deployment.**
Подставьте в умолчание значение константы литералом или вызовом функции,
которая его возвращает.

Реализовано: `ora2pg_gap_report/detectors/package_constant_default.py` -
голое имя или имя с префиксом пакета в умолчании параметра подпрограммы
в спецификации или теле пакета. Объявление имени в том же файле не
требуется: тело часто выгружают без спецификации.
