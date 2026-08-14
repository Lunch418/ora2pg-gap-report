# Пример: детектор `autonomous_tx` на реальном пакете

Вход: `docs/research/samples/logger.pkb` (OraOpenSource/Logger,
package body `LOGGER`, ≈3300 строк).

Команда:

```python
from pathlib import Path
from src.detectors.autonomous_tx import find_autonomous_transactions
from src.report_generator import to_markdown

source = Path("docs/research/samples/logger.pkb").read_text()
findings = find_autonomous_transactions(source)
print(to_markdown(findings))
```

Результат — 8 из 8 реальных вхождений `PRAGMA AUTONOMOUS_TRANSACTION` в
пакете найдены, без ложных срабатываний (проверено также на
`sql_util_pkg.pkb`/`file_util_pkg.pkb`, где этой прагмы нет вообще — там
детектор возвращает пустой список).

| Объект | Строка | Серьёзность | Фрагмент | Комментарий |
|---|---|---|---|---|
| `LOGGER.SAVE_GLOBAL_CONTEXT` | 214 | high | `pragma autonomous_transaction;` | ora2pg перенесёт эту процедуру/функцию через dblink-обёртку (переименует в *_atx, уберёт COMMIT из тела, добавит функцию-прокси, вызывающую её через dblink()). Стратегия рабочая, но не бесшовная: требуется расширение dblink и ручная настройка connection string — то есть сетевая зависимость между процедурами, которая может быть неприемлема в контуре с жёсткими требованиями к изоляции. При этом SHOW_REPORT и --estimate_cost систематически недооценивают стоимость этой конструкции именно для функций/процедур внутри PACKAGE BODY — сама PRAGMA стоит в декларативной секции (до BEGIN), которая не попадает в подсчёт стоимости (declare/code split в Ora2Pg.pm::_lookup_function). |
| `LOGGER.NULL_GLOBAL_CONTEXTS` | 822 | high | `pragma autonomous_transaction;` | (то же объяснение) |
| `LOGGER.LOG_APEX_ITEMS` | 1649 | high | `pragma autonomous_transaction;` | (то же объяснение) |
| `LOGGER.PURGE` | 2115 | high | `pragma autonomous_transaction;` | (то же объяснение) |
| `LOGGER.PURGE_ALL` | 2178 | high | `pragma autonomous_transaction;` | (то же объяснение) |
| `LOGGER.SET_LEVEL` | 2356 | high | `pragma autonomous_transaction;` | (то же объяснение) |
| `LOGGER.UNSET_CLIENT_LEVEL` | 2461 | high | `pragma autonomous_transaction;` | (то же объяснение) |
| `LOGGER.INS_LOGGER_LOGS` | 2782 | high | `pragma autonomous_transaction;` | (то же объяснение) |

Полный текст комментария одинаков для всех строк — сокращён здесь для
читаемости, см. `src/detectors/autonomous_tx.py::_MESSAGE`.
