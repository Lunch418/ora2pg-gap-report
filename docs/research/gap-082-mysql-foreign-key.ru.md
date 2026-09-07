# GAP-082: `FOREIGN KEY` выбрасывается на файловом пути

MySQL/MariaDB feature: внешний ключ, объявляемый в списке столбцов
`CREATE TABLE`.

## Минимальный пример

В том виде, в каком его пишет `mysqldump`:

```sql
CREATE TABLE `customers` (
  `id` int(11) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;
CREATE TABLE `orders2` (
  `id` int(11) NOT NULL,
  `customer_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_orders_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB;
```

## Вывод ora2pg, файловый путь (v25.0, `-m -i schema.sql -t TABLE`)

```sql
CREATE TABLE orders2 (
	id integer NOT NULL,
	customer_id integer NOT NULL
) ;
ALTER TABLE orders2 ADD PRIMARY KEY (id);
```

Строк `FOREIGN KEY` во всём сгенерированном файле — ноль (проверено
`grep -c`). Ни внутри `CREATE TABLE`, ни отдельным `ALTER TABLE` после
него. То же самое для формы без имени ограничения (`FOREIGN KEY (pid)
REFERENCES parent7 (id)`) — тоже ноль.

## Та же схема против живой MySQL: FK на месте

Это исправление к более ранней версии документа, где потеря
объяснялась отсутствием у `-t` типа экспорта под внешние ключи. Это
объяснение было неверным, и разрыв нашёл читатель, проверивший его
на реальном прогоне `ora2pg -m -t TABLE` против живой базы, а не против
файлового входа `-i`, который сканирует этот проект: загрузил ровно
такую же схему в реальную MariaDB, натравил `ora2pg -m` на неё через
живое соединение вместо файла, и тот же самый `-t TABLE` выдал

```sql
CREATE TABLE orders2 (
	id integer NOT NULL,
	customer_id integer NOT NULL
) ;
CREATE INDEX fk_orders_customer ON orders2 (customer_id);
ALTER TABLE orders2 ADD PRIMARY KEY (id);
ALTER TABLE orders2 ADD CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customers(id) MATCH SIMPLE ON DELETE CASCADE ON UPDATE RESTRICT;
```

Внешний ключ есть, отдельным `ALTER TABLE ADD CONSTRAINT`. Повторено
независимо при исправлении этого документа: та же схема, тот же
`-t TABLE`, на этот раз живая MariaDB 10.11, та же строка
`ALTER TABLE ADD CONSTRAINT`. То есть `-t TABLE` действительно
экспортирует внешние ключи, а прежнее утверждение об отсутствии
подходящего типа `-t` отвечало не на тот вопрос.

## Почему файловый путь всё равно теряет его

Прочитан `MySQL.pm::_foreign_key()` (ora2pg 25.0, `lib/Ora2Pg/MySQL.pm`,
строка 607), чтобы найти настоящий механизм, а не гадать заново. Вся
функция — это один безусловный живой запрос:

```perl
sub _foreign_key
{
        my ($self, $table, $owner) = @_;
        ...
	my $sql = "SELECT DISTINCT A.COLUMN_NAME, ... FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS A
                    INNER JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS AS B ...";
        my $sth = $self->{dbh}->prepare($sql) or $self->logit("FATAL: " . $self->{dbh}->errstr . "\n", 0, 1);
        $sth->execute or $self->logit("FATAL: " . $sth->errstr . "\n", 0, 1);
        ...
}
```

`$self->{dbh}` — это живой хендл подключения DBI. Ни в этой функции, ни
где-либо ещё в `MySQL.pm` нет ветки, которая разбирала бы `FOREIGN KEY
(...) REFERENCES ...` из текста DDL. Внешние ключи — это метаданные,
которые ora2pg вообще только и делает, что спрашивает у живого
`INFORMATION_SCHEMA`. На файловом пути (`-i <file>`, без `ORACLE_DSN`)
никакого `$self->{dbh}` нет, поэтому эта функция просто не достигается
ни с чем, что можно было бы вернуть, сколько бы ни было в файле
`CONSTRAINT ... FOREIGN KEY`.

`PRIMARY KEY` переживает тот же самый файловый прогон (см. строку
`ALTER TABLE orders2 ADD PRIMARY KEY (id);` выше), потому что читается
по-другому — из метаданных столбцов формы `DESCRIBE`, которые
`mysqldump`-подобные инструменты уже кладут рядом с каждым столбцом, а
не из join по `KEY_COLUMN_USAGE`. Внешние ключи в этом кодовой базе —
единственная связь, которая существует только в собственном каталоге
базы данных.

## Наблюдаемая проблема

Для пользователя, который работает так, как заявляет README этого
проекта (уже выгруженный файл DDL/дампа, без живого доступа к базе —
собственно ради этого `ora2pg-gap-report` и существует, для air-gapped
и офлайн-миграций), ошибки не будет ни на загрузке, ни потом. Схема
поднимется, приложение заработает, и ссылочная целостность просто
перестанет существовать — вместе с каскадными удалениями, если они
были. Заметить это можно только по последствиям: осиротевшие строки,
которые база раньше не позволяла создать.

Пользователь, который вместо этого натравливает `ora2pg -m` на живую
MySQL/MariaDB, с этим вообще не столкнётся: внешние ключи экспортируются
корректно, как показано выше. Это ограничение именно файлового пути, а
не `ora2pg -m` вообще, и `-t TABLE` для MySQL/MariaDB не лишён поддержки
внешних ключей — он просто не может до неё дотянуться без базы, которую
можно спросить.

**Reproducible: YES**, на файловом пути, который сканирует этот проект.
Ora2Pg version: 25.0, PostgreSQL 16. Source dialect: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён для файлового входа, severity high, failure_stage
semantic.** По классу это ровно то, что README называет «архитектурно
значимой потерей»: гарантия, объявленная в определении объекта,
исчезает бесследно — родственно GAP-066 (`WITH READ ONLY`) и GAP-026
(`READ ONLY` на таблице). Восстанавливается вручную: `ALTER TABLE
<таблица> ADD CONSTRAINT <имя> FOREIGN KEY (<столбцы>) REFERENCES
<родитель> (<столбцы>) ON DELETE ...` после загрузки всех таблиц, либо
экспортом через живое подключение к исходной базе вместо файла —
механизм выше показывает, что это само по себе решает именно эту
находку. Реализовано: `ora2pg_gap_report/detectors/mysql_foreign_key.py`.
