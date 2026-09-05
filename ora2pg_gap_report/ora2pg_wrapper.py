"""Thin wrapper around the real `ora2pg` binary.

Deliberately per-object-type (`-t PACKAGE`, `-t TRIGGER`, ...), not
`-t SHOW_REPORT`: the research in docs/research/step0-show-report-baseline.md
found SHOW_REPORT itself has no offline mode — it always requires a live
Oracle connection (ORACLE_DSN), even though individual object types accept
a plain DDL file (`-i file.sql`). That's what our target audience (closed
networks, air-gapped environments) can actually use, so that's the only
mode this wrapper supports.

Requires a working `ora2pg` install on PATH (or pass ora2pg_bin=). Not
installable via pip — it's a Perl tool, not a Python package; see README
for setup.

Parses ora2pg's --estimate_cost output by matching its exact comment-line
text format ("-- Function X total estimated cost: N", "-- Total estimated
cost: N units, M person-day(s)", etc. — see the _*_RE patterns below).
That format is ora2pg's own, not a stable interface this project
controls or ora2pg documents as one — a future ora2pg release that
rewords its output would make these regexes silently stop matching
(count as "nothing found", not raise an error). Confirmed against the
ora2pg version this project researches against (gap_registry.py's
ora2pg_version), not re-verified automatically against newer releases.
"""

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import i18n


class Ora2PgNotFoundError(RuntimeError):
    """The ora2pg executable could not be located/started."""


class Ora2PgRunError(RuntimeError):
    """ora2pg started but exited with a non-zero status, or timed out."""


@dataclass(frozen=True)
class FunctionCost:
    name: str
    total_cost: float
    # keyword (e.g. "DBMS_", "CONNECT BY") -> occurrence count
    breakdown: dict[str, int]


_FUNCTION_COST_RE = re.compile(
    # -t PACKAGE: "... total estimated cost: N"
    # -t FUNCTION/PROCEDURE: "... estimated cost: N" (no "total")
    r"--\s*Function\s+(\S+)\s+(?:total\s+)?estimated cost:\s*([\d.]+)",
    re.IGNORECASE,
)
_KEYWORD_COST_RE = re.compile(r"^--\s*([A-Za-z_ ]+?)\s*=>\s*(\d+)")
_TOTAL_RE = re.compile(
    # -t PACKAGE: "Total estimated cost for package NAME: N units, M person-day(s)"
    # -t FUNCTION/PROCEDURE: "Total estimated cost: N units, M person-day(s)." (no package name)
    r"--\s*Total estimated cost(?:\s+for package\s+(\S+))?:\s*([\d.]+)\s*units,"
    r"\s*([\d.]+)\s*person-day",
    re.IGNORECASE,
)


# `ora2pg --version` prints a single line, e.g. "Ora2Pg v25.0". Matched
# loosely on purpose: the point is to read a version out of whatever it
# prints, and a wording change should degrade to "unknown" rather than to
# a wrong answer.
_VERSION_RE = re.compile(r"\bv?(\d+\.\d+(?:\.\d+)?)\b")


def _first_lines(text: str, limit: int = 5) -> str:
    """The first few non-empty lines of `text`.

    For ora2pg's fatal-error output, which is one useful line followed by
    its entire usage screen -- a hundred lines of flag documentation is
    not what someone wants to read out of an error message."""
    lines = [line for line in (text or "").splitlines() if line.strip()]
    return "\n".join(lines[:limit])


def installed_version(ora2pg_bin: str = "ora2pg", timeout: int = 15) -> str | None:
    """The version of the ora2pg on PATH, or None if it can't be
    determined.

    None covers every "can't tell" case -- not installed, not runnable,
    too slow, or output this doesn't recognise -- because every caller
    treats them the same way: say nothing rather than guess. A version
    check that reported a wrong version would be worse than no check,
    since the whole point of it is to tell the user when the findings
    they are reading were verified against different software than they
    have.
    """
    try:
        result = subprocess.run(
            [ora2pg_bin, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    # Some builds print the banner to stderr; check both rather than
    # assuming which.
    match = _VERSION_RE.search(f"{result.stdout}\n{result.stderr}")
    return match.group(1) if match else None


def run_estimate_cost(
    input_file: Path,
    object_type: str,
    ora2pg_bin: str = "ora2pg",
    timeout: int = 120,
    lang: str = "ru",
) -> str:
    """Run `ora2pg -t <object_type> -i <input_file> --estimate_cost` and
    return the generated output as text (empty string if ora2pg found
    nothing of that type in the file — it doesn't always write the output
    file in that case)."""
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "out.sql"
        try:
            result = subprocess.run(
                [
                    ora2pg_bin,
                    "-t", object_type,
                    "-i", str(input_file),
                    "--estimate_cost",
                    "-o", out_path.name,
                    "-b", tmp,
                ],
                capture_output=True,
                text=True,
                # Explicit, not the locale default: text=True alone decodes
                # with locale.getpreferredencoding(), which is cp1252 on a
                # default Windows install. ora2pg's own output is UTF-8 and
                # routinely non-ASCII, and result.stderr gets embedded in
                # the error messages below -- so the locale default turns a
                # readable ora2pg failure into a UnicodeDecodeError from
                # inside subprocess. errors="replace" for the same reason
                # the scanned files are read that way: a mis-encoded byte
                # somewhere in a diagnostic is not a reason to fail.
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except OSError as exc:
            # Covers FileNotFoundError (binary missing) as well as
            # PermissionError/IsADirectoryError (e.g. a bad --ora2pg-bin) —
            # all of these mean "couldn't even start ora2pg", which callers
            # are meant to treat the same way: skip this check gracefully.
            raise Ora2PgNotFoundError(
                i18n.t(lang, "ora2pg_not_runnable", bin=repr(ora2pg_bin), exc=exc)
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise Ora2PgRunError(i18n.t(lang, "ora2pg_timeout", timeout=timeout)) from exc

        if result.returncode != 0:
            # stderr first, but not only: ora2pg writes its fatal errors to
            # *stdout* -- "FATAL: can't find configuration file
            # /etc/ora2pg/ora2pg.conf", followed by its usage text -- and
            # exits 1 with stderr empty. Reporting stderr alone turned the
            # single most common ora2pg failure, a missing config, into
            # "ora2pg завершился с кодом 1:" and nothing else. Found by the
            # CI job that runs the real binary, which is what that job is
            # for. The usage dump that follows the FATAL line is noise, so
            # only the first few lines are kept.
            detail = (result.stderr or "").strip() or _first_lines(result.stdout)
            raise Ora2PgRunError(
                i18n.t(lang, "ora2pg_failed", code=result.returncode, detail=detail)
            )
        if not out_path.exists():
            return ""
        return out_path.read_text(encoding="utf-8", errors="replace")


def parse_function_costs(ora2pg_output: str) -> list[FunctionCost]:
    """Parse the '-- Detailed cost per function' block ora2pg emits with
    --estimate_cost into structured per-function cost + keyword breakdown.
    """
    functions: list[FunctionCost] = []
    name = None
    total = 0.0
    breakdown: dict[str, int] = {}

    for line in ora2pg_output.splitlines():
        func_match = _FUNCTION_COST_RE.search(line)
        if func_match:
            if name is not None:
                functions.append(FunctionCost(name, total, breakdown))
            name = func_match.group(1)
            total = float(func_match.group(2))
            breakdown = {}
            continue
        if name is not None:
            kw_match = _KEYWORD_COST_RE.match(line.strip())
            if kw_match:
                breakdown[kw_match.group(1).strip().upper()] = int(kw_match.group(2))

    if name is not None:
        functions.append(FunctionCost(name, total, breakdown))

    return functions


def parse_totals(ora2pg_output: str) -> list[tuple[str | None, float, float]]:
    """Return (package_name_or_None, total_units, person_days) for every
    "Total estimated cost..." summary line in the output. -t PACKAGE mode
    emits one such line per package (named); -t FUNCTION/PROCEDURE mode
    emits one unnamed line for the whole run. A list, not a single value —
    a -t PACKAGE run against a multi-package DDL file emits one such line
    per package, not just one."""
    return [
        (m.group(1), float(m.group(2)), float(m.group(3)))
        for m in _TOTAL_RE.finditer(ora2pg_output)
    ]
