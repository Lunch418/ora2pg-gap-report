*[English](ci-integration.md) | Русский*

# CI-интеграция

Два рецепта: как встроить `ora2pg-gap-report` в пайплайн миграции рядом с
`ora2pg`, и как получить находки прямо построчно в GitHub PR — без своего
Action и без своего бота, силами самого GitHub.

## Пайплайн вместе с ora2pg

`ora2pg-gap-report` не заменяет `ora2pg` и не встраивается в него — это
отдельный шаг до и после конвертации:

```sh
# 1. До конвертации: гейт на Oracle-исходник. Останавливает пайплайн,
#    если есть high-находки — не тратим время на конвертацию схемы,
#    которую и так придётся чинить руками.
ora2pg-gap-report schema/ --save baseline.json --fail-on high

# 2. Конвертация самим ora2pg — как обычно.
ora2pg -c ora2pg.conf -t COPY

# 3. Опционально: реальный прогон ora2pg на CONNECT BY-конструкциях —
#    проверка конкретного известного бага в сгенерированном WITH RECURSIVE
#    (требует установленный ora2pg, см. README, "Optional: lint...").
ora2pg-gap-report schema/ --check-connect-by

# 4. После конвертации: сравнить, что из baseline реально осталось в уже
#    сгенерированном PostgreSQL-коде — не гипотеза, а STILL_PRESENT/
#    NOT_DETECTED/NOT_VERIFIABLE по факту.
ora2pg-gap-report --verify --baseline baseline.json generated_postgresql/
```

Шаг 4 — статическая проверка (детекторы повторно прогоняются на
сгенерированном файле), не поведенческая: она не подключается к БД и
ничего не выполняет. Подробности и список `NOT_VERIFIABLE`-детекторов — в
разделе README про `--verify`.

## Находки прямо в GitHub PR (без своего бота)

`--format sarif` — не просто ещё один формат вывода. SARIF 2.1.0 — формат,
который GitHub понимает нативно через `github/codeql-action/upload-sarif`:
результаты появляются во вкладке **Security → Code scanning alerts**, а на
PR, где сработал сам workflow (`on: pull_request`), — построчными
аннотациями на изменённых строках диффа. Специального Action или бота
писать не нужно.

```yaml
# .github/workflows/migration-gap-scan.yml
name: migration-gap-scan

on:
  pull_request:
    paths:
      - "schema/**"

permissions:
  contents: read
  security-events: write   # обязателен для загрузки SARIF

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - run: pip install ora2pg-gap-report

      # Гейт: явно ломает джобу, если есть high-находка. SARIF отдельно
      # ничего не гейтит сам по себе — только показывает находки.
      - name: Gate on high-severity findings
        run: ora2pg-gap-report schema/ --fail-on high

      # SARIF грузится отдельным шагом, даже если гейт выше упал —
      # чтобы аннотации всё равно появились в PR для разбора.
      - name: Generate SARIF report
        if: always()
        run: ora2pg-gap-report schema/ --format sarif --output results.sarif

      - name: Upload to GitHub code scanning
        if: always()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: results.sarif
```

Оговорки, чтобы не переобещать:

- На приватных репозиториях загрузка SARIF в code scanning требует GitHub
  Advanced Security (на публичных — бесплатно). Для этого проекта не
  актуально (репозиторий публичный), но важно для тех, кто переносит
  рецепт в закрытый корпоративный репозиторий.
- Построчные аннотации в самом PR появляются для находок на строках,
  входящих в дифф. Находки вне диффа (например, в файле, который PR не
  трогает) видны во вкладке Security, но не подсвечиваются построчно в
  Files changed.
- GitLab SAST использует свой собственный JSON-формат отчёта, не SARIF
  напрямую — просто загрузить `results.sarif` как GitLab SAST-артефакт не
  получится. Точный путь конвертации SARIF → формат GitLab здесь не
  проверялся, поэтому не приводится как готовый рецепт — если понадобится,
  это отдельная, некрупная задача.
