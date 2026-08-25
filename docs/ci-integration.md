*English | [Русский](ci-integration.ru.md)*

# CI integration

Two recipes: how to fit `ora2pg-gap-report` into a migration pipeline
alongside `ora2pg`, and how to get findings inline, line by line, in a
GitHub PR, with no custom Action and no custom bot, using GitHub's own
features.

## A pipeline alongside ora2pg

`ora2pg-gap-report` doesn't replace `ora2pg` and doesn't hook into it,
it's a separate step before and after conversion:

```sh
# 1. Before conversion: gate on the Oracle source. Stops the pipeline if
#    there are high-severity findings -- no point spending time
#    converting a schema that will need manual fixing anyway.
ora2pg-gap-report schema/ --save baseline.json --fail-on high

# 2. Conversion via ora2pg itself -- as usual.
ora2pg -c ora2pg.conf -t COPY

# 3. Optional: a real ora2pg run against CONNECT BY constructs -- checks
#    a specific known bug in the generated WITH RECURSIVE (requires
#    ora2pg installed, see the README, "Optional: lint...").
ora2pg-gap-report schema/ --check-connect-by

# 4. After conversion: compare what from the baseline is actually still
#    there in the already-generated PostgreSQL code -- not a guess, an
#    actual STILL_PRESENT/NOT_DETECTED/NOT_VERIFIABLE answer.
ora2pg-gap-report --verify --baseline baseline.json generated_postgresql/
```

Step 4 is a static check (the detectors are simply re-run against the
generated file), not a behavioral one: it never connects to a database
and never executes anything. Details and the list of `NOT_VERIFIABLE`
detectors are in the README's `--verify` section.

## Findings inline in a GitHub PR (no custom bot)

`--format sarif` isn't just another output format. SARIF 2.1.0 is a
format GitHub understands natively via
`github/codeql-action/upload-sarif`: results show up under **Security →
Code scanning alerts**, and on the PR that triggered the workflow itself
(`on: pull_request`), as inline annotations on the diff's changed lines.
No custom Action or bot needed.

```yaml
# .github/workflows/migration-gap-scan.yml
name: migration-gap-scan

on:
  pull_request:
    paths:
      - "schema/**"

permissions:
  contents: read
  security-events: write   # required to upload SARIF

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - run: pip install ora2pg-gap-report

      # Gate: explicitly fails the job if there's a high-severity finding.
      # SARIF on its own doesn't gate anything, it only shows findings.
      - name: Gate on high-severity findings
        run: ora2pg-gap-report schema/ --fail-on high

      # SARIF is uploaded as a separate step, even if the gate above
      # failed, so the annotations still show up in the PR for review.
      - name: Generate SARIF report
        if: always()
        run: ora2pg-gap-report schema/ --format sarif --output results.sarif

      - name: Upload to GitHub code scanning
        if: always()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: results.sarif
```

Caveats, so this doesn't overpromise:

- On private repositories, uploading SARIF to code scanning requires
  GitHub Advanced Security (free on public ones). Doesn't apply to this
  project (the repository is public), but matters for anyone porting
  this recipe into a closed corporate repository.
- Inline annotations in the PR itself only show up for findings on lines
  that are part of the diff. Findings outside the diff (e.g. in a file
  the PR doesn't touch) are visible under the Security tab, but aren't
  highlighted inline in Files changed.
- GitLab SAST uses its own JSON report format, not SARIF directly, so
  just uploading `results.sarif` as a GitLab SAST artifact won't work.
  The exact SARIF → GitLab format conversion path hasn't been checked
  here, so it isn't given as a ready recipe, if it's ever needed, that's
  a separate, small task.
