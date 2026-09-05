# Example: the `autonomous_tx` detector on a real package

Input: `docs/research/samples/logger.pkb` (OraOpenSource/Logger, package
body `LOGGER`, ≈3300 lines).

Command:

```python
from pathlib import Path
from ora2pg_gap_report.detectors.autonomous_tx import find_autonomous_transactions
from ora2pg_gap_report.report_generator import to_markdown

source = Path("docs/research/samples/logger.pkb").read_text()
findings = find_autonomous_transactions(source)
print(to_markdown(findings))
```

Result — all 8 of the 8 real occurrences of `PRAGMA
AUTONOMOUS_TRANSACTION` in the package are found, with no false positives
(also checked on `sql_util_pkg.pkb`/`file_util_pkg.pkb`, which contain no
such pragma at all — there the detector returns an empty list).

| Object | Line | Severity | Fragment | Comment |
|---|---|---|---|---|
| `LOGGER.SAVE_GLOBAL_CONTEXT` | 214 | high | `pragma autonomous_transaction;` | ora2pg will port this procedure/function through a dblink wrapper (renaming it to *_atx, removing the COMMIT from the body, and adding a proxy function that calls it over dblink()). The strategy works, but it is not seamless: it needs the dblink extension and a manually configured connection string — that is, a network dependency between procedures, which may be unacceptable in an environment with strict isolation requirements. On top of that, SHOW_REPORT and --estimate_cost systematically underestimate the cost of this construct specifically for functions and procedures inside a PACKAGE BODY — the PRAGMA itself sits in the declarative section (before BEGIN), which is not included in the cost computation (the declare/code split in Ora2Pg.pm::_lookup_function). |
| `LOGGER.NULL_GLOBAL_CONTEXTS` | 822 | high | `pragma autonomous_transaction;` | (the same explanation) |
| `LOGGER.LOG_APEX_ITEMS` | 1649 | high | `pragma autonomous_transaction;` | (the same explanation) |
| `LOGGER.PURGE` | 2115 | high | `pragma autonomous_transaction;` | (the same explanation) |
| `LOGGER.PURGE_ALL` | 2178 | high | `pragma autonomous_transaction;` | (the same explanation) |
| `LOGGER.SET_LEVEL` | 2356 | high | `pragma autonomous_transaction;` | (the same explanation) |
| `LOGGER.UNSET_CLIENT_LEVEL` | 2461 | high | `pragma autonomous_transaction;` | (the same explanation) |
| `LOGGER.INS_LOGGER_LOGS` | 2782 | high | `pragma autonomous_transaction;` | (the same explanation) |

The full text of the comment is identical for every row — abbreviated
here for readability, see
`ora2pg_gap_report/detectors/autonomous_tx.py::_MESSAGE`.
