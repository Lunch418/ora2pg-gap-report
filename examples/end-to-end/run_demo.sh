#!/usr/bin/env bash
# Walks through the whole SCAN -> migrate -> VERIFY lifecycle this tool is
# built around, using one real, reproducible example (GAP-003, see
# docs/research/gap-003-bulk-collect-forall.md) end to end instead of in
# isolated pieces. See README.md in this directory for what each step means
# and why there's no single VERIFY "PASS/FAIL" exit code -- that's
# deliberate, not missing.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if ! command -v ora2pg-gap-report >/dev/null 2>&1; then
  echo "ora2pg-gap-report isn't installed. Run this from a repo checkout with" >&2
  echo "'pip install -e .' first, or 'pip install ora2pg-gap-report'." >&2
  exit 2
fi

echo "==> Step 1/4: scan the Oracle source, gate the migration on it"
echo "    \$ ora2pg-gap-report oracle/ --fail-on high --lang en"
echo
scan_exit=0
ora2pg-gap-report oracle/ --fail-on high --lang en || scan_exit=$?
echo
echo "    exit code: $scan_exit (1 = gate FAILED, matches --fail-on high finding real issues)"
if [ "$scan_exit" -ne 1 ]; then
  echo "    UNEXPECTED: expected exit code 1 here -- something about this example changed." >&2
  exit 1
fi
echo

echo "==> Step 2/4: save that scan as a baseline (this is what generated baseline.json)"
echo "    \$ ora2pg-gap-report oracle/ --save baseline.json --lang en"
echo "    (already committed in this directory -- not re-run, to keep this script read-only)"
echo

echo "==> Step 3/4: migrate with ora2pg, then VERIFY the *generated* PostgreSQL output"
if command -v ora2pg >/dev/null 2>&1; then
  echo "    ora2pg found on PATH -- regenerating generated/bulk_test_pkg.sql for real"
  tmp_out="$(mktemp -d)"
  ora2pg -t PACKAGE -i oracle/bulk_test_pkg.sql -o out.sql -b "$tmp_out" >/dev/null 2>&1
  if ! diff -q "$tmp_out/out.sql" generated/bulk_test_pkg.sql >/dev/null 2>&1; then
    echo "    NOTE: freshly-generated output differs from the committed fixture" >&2
    echo "    (a different ora2pg version than 25.0, most likely) -- diff:" >&2
    diff "$tmp_out/out.sql" generated/bulk_test_pkg.sql >&2 || true
  else
    echo "    confirmed: matches the committed generated/bulk_test_pkg.sql exactly"
  fi
  rm -rf "$tmp_out"
else
  echo "    ora2pg not found on PATH -- using the committed generated/bulk_test_pkg.sql"
  echo "    (real ora2pg 25.0 output, not fabricated -- see this file's own header comment)"
fi
echo
echo "    \$ ora2pg-gap-report --verify --baseline baseline.json generated/ --lang en"
echo
ora2pg-gap-report --verify --baseline baseline.json generated/ --lang en
echo
echo "    STILL_PRESENT is the honest answer here: the migration didn't fix anything yet."
echo

echo "==> Step 4/4: after a real manual fix (generated_fixed/), VERIFY again"
echo "    \$ ora2pg-gap-report --verify --baseline baseline.json generated_fixed/ --lang en"
echo
ora2pg-gap-report --verify --baseline baseline.json generated_fixed/ --lang en
echo
echo "    NOT_DETECTED here means what it always means: the pattern is gone, not"
echo "    'provably correct' -- generated_fixed/bulk_test_pkg.sql was also confirmed"
echo "    against a real PostgreSQL 16 server (see README.md's 'Verified against a"
echo "    real server' section for the exact commands)."
echo
echo "Done -- SCAN found it, VERIFY confirmed it survived migration, then confirmed"
echo "the fix actually removed it."
