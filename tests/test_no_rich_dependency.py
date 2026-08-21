"""Guards the claim pyproject.toml and README both make: the detector
library itself (models.py, detectors/, report_generator.py, baseline.py)
doesn't depend on rich -- only the terminal/interactive-picker paths do.

Runs in a subprocess with a meta_path hook that raises on any `import
rich`, rather than monkeypatching sys.modules in-process: several other
tests in this suite legitimately import rich (terminal_report.py and
friends), and a process-wide block would poison them depending on test
order. The subprocess is throwaway and doesn't touch the real test
session's import state at all."""

import subprocess
import sys

_GUARD_SCRIPT = """
import sys, importlib.abc

class _BlockRich(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name == "rich" or name.startswith("rich."):
            raise ImportError(f"rich blocked: {name}")
        return None

sys.meta_path.insert(0, _BlockRich())

import ora2pg_gap_report.models
import ora2pg_gap_report.detectors.bulk_collect
import ora2pg_gap_report.report_generator
import ora2pg_gap_report.baseline
import ora2pg_gap_report.effort_estimator
import ora2pg_gap_report.gap_registry
print("OK")
"""


def test_core_modules_import_without_rich_installed():
    result = subprocess.run(
        [sys.executable, "-c", _GUARD_SCRIPT], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"
