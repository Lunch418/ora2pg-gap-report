import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def _wide_terminal_for_rich_output(monkeypatch):
    """Rich (used by cli.py's terminal/error output) picks a terminal width
    from COLUMNS when stdout/stderr aren't a real tty, which is always true
    under pytest. Left unpinned, the effective width varies by environment
    — confirmed: this sandbox and GitHub Actions runners detect different
    widths, and the longer absolute paths under CI wrap file names across
    lines — making substring assertions against captured rich output flaky
    depending on where the suite runs."""
    monkeypatch.setenv("COLUMNS", "200")
