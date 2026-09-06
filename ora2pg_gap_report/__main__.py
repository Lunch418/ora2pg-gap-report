"""Entry point for `python -m ora2pg_gap_report`.

The package installs two console scripts (see [project.scripts] in
pyproject.toml), and those stay the documented way in. This module exists
for the case they are not on PATH: a checkout that was never `pip
install`ed, a `pip install --user` whose script directory is not on PATH,
or a CI step that would rather call the interpreter it just resolved than
trust PATH. Without it, `python -m ora2pg_gap_report` fails with
"cannot be directly executed", which reads as "this tool is broken"
rather than "use the other command".

Deliberately just a delegation to cli.main() -- the argument parsing,
exit codes and error handling all live there, so both ways in behave
identically rather than drifting apart.
"""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
