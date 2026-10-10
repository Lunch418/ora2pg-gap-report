# GAP-129: `''` в Oracle - это NULL, в PostgreSQL - пустая строка

Возможность Oracle: строковый литерал нулевой длины - это NULL. `x = ''`
никогда не истинно, после `v := ''` переменная `v` равна NULL, `DEFAULT ''`
не задаёт никакого значения, а `NVL(p, '')` возвращает NULL.

## Как найдено

Из внешнего отзыва об инструменте: всё, что он находил, падало при
загрузке, и ничего - из того, что загружается, а потом работает иначе.
`''` против NULL - самое известное различие такого рода, его проверили
первым.

## Минимальный пример

`tests/fixtures/empty_string_null/oracle_source.sql`, VALID в живом
Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_e2(p VARCHAR2) RETURN VARCHAR2 IS
BEGIN
  IF p = '' THEN RETURN 'empty'; END IF;
  RETURN 'other';
END;
/
CREATE OR REPLACE FUNCTION gx_e5(p VARCHAR2) RETURN VARCHAR2 IS
  v VARCHAR2(10) := '';
BEGIN
  IF v IS NULL THEN RETURN 'v is null'; END IF;
  RETURN 'v is not null';
END;
/
CREATE TABLE gx_notes (id NUMBER, note VARCHAR2(20) DEFAULT '');
CREATE OR REPLACE FUNCTION gx_e6(p VARCHAR2) RETURN VARCHAR2 IS
BEGIN
  RETURN NVL(p, '');
END;
/
```

и ещё три функции, которые только передают значения дальше (`p IS NULL`,
`a || b`, `LENGTH(p)`), - чтобы посмотреть, что происходит с аргументом
`''`.

## Вывод ora2pg (v25.0, `-t FUNCTION`, `-t TABLE`)

`tests/fixtures/empty_string_null/ora2pg_output.sql`. Всё копируется как
есть, кроме NVL:

```sql
  IF p = '' THEN RETURN 'empty';END IF;
  v varchar(10) := '';
	note varchar(20) DEFAULT ''
  RETURN coalesce(p, '');
```

У ora2pg есть опция `NULL_EQUAL_EMPTY`, которая переписывает сравнения с
`''`; по умолчанию она выключена и здесь была выключена.

## Наблюдаемая проблема

Всё загружается в PostgreSQL 16 без ошибок, а затем:

| Вызов | Oracle 23ai | PostgreSQL 16 |
|---|---|---|
| `gx_e2('')` | `other` | `empty` |
| `gx_e5('x')` | `v is null` | `v is not null` |
| `INSERT INTO gx_notes (id) VALUES (1)`, строк с `note IS NULL` | 1 | 0 (`note` равно `''`) |
| `gx_e6(NULL) IS NULL` | да | нет (`''`) |
| `gx_e1('')` (`p IS NULL`) | `null` | `value` |
| `gx_e3('a', NULL)` (`a \|\| b`) | `a` | NULL |
| `gx_e4('')` (`LENGTH`) | NULL | 0 |

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage semantic.** Ничего не
падает - отличаются результаты.

Что можно найти по тексту: пустой литерал в сравнении (`=`, `<>`, `!=`,
`^=`, с любой стороны), в присваивании (`:=`), в `DEFAULT` или как
запасное значение `NVL`/`COALESCE`. Это детектор и сообщает. Остальные три
строки таблицы - `IS NULL` для значения, пришедшего как `''`, склейка с
NULL, `LENGTH('')` - зависят от данных, а не от кода, и по исходнику их не
отличить от обычного использования; их оставляем тестированию.

Присваивание (`v := ''`) или значение параметра по умолчанию (`p VARCHAR2
DEFAULT ''`) помечается, только если та же подпрограмма - или, для
переменной пакета, пакет - проверяет это имя на NULL (`IS [NOT] NULL`,
`NVL`, `COALESCE`, `DECODE`, `LENGTH`): `v := ''; v := v || x` одинаково
в обеих базах, и на реальном коде (библиотека Alexandria PL/SQL,
oos-utils, utPLSQL) таких было большинство. `DEFAULT ''` у столбца,
сравнение и `NVL(x, '')` помечаются всегда.

Механического исправления нет: должно ли `x = ''` стать `x IS NULL` или
`coalesce(x, '') = ''`, зависит от того, могут ли данные в PostgreSQL
содержать пустые строки. `--verify` повторно запускает детектор на выводе:
ora2pg сохраняет все формы, а NVL - как `coalesce(x, '')`, который детектор
тоже находит.

Реализовано: `ora2pg_gap_report/detectors/empty_string_null.py`.
