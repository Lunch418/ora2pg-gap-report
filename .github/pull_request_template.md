## What changes and why

<!-- Briefly: what the finding/feature is, and why it is needed -->

## Checklist

- [ ] `pytest` — green
- [ ] `ruff check ora2pg_gap_report/ tests/ scripts/` — green
- [ ] `python3 scripts/doctor.py` — green
- [ ] For a new detector: the hypothesis is confirmed by a real `ora2pg`
      run (not from the documentation), there is at least one positive
      test and one guard test against false positives, and a research
      document has been added to `docs/research/` and registered in
      `gap_registry.py`
- [ ] CHANGELOG.md updated
