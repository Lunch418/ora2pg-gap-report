"""Baseline snapshots — track findings across repeated scans of a schema
that keeps changing during a migration project (fix some gaps, re-scan,
see what's left).

A finding's identity across two scans can't be its line number: lines
shift on any unrelated edit anywhere in the file, not just edits to the
flagged construct itself. Instead each finding is grouped by what
actually identifies *what* was found, not *where* on the page: which
detector found it, which file, which object, and the flagged fragment
(snippet).

Findings within a group are genuinely indistinguishable from each other
by that definition (e.g. the same DBMS_LOB call appearing on two
different lines of the same package) -- nothing in the Finding model
gives them a more specific identity. An earlier version of this module
tried to disambiguate them anyway with a per-occurrence index baked into
the fingerprint, which looked stable but wasn't: fixing just one of two
identical findings between scans shifts the survivor's occurrence index
down, so it silently matches the *other* one's baseline record instead --
reporting the wrong instance as resolved and hiding the one that
actually was. Comparing group counts instead (this module's actual
approach) sidesteps the problem instead of half-solving it: it never
claims to know *which* specific instance was fixed, only how many were,
which is the only thing that's actually knowable here."""

import dataclasses
import hashlib
import json
from pathlib import Path

from .models import Finding

SCHEMA_VERSION = 1


class BaselineLoadError(Exception):
    """A --baseline file couldn't be read or isn't in the expected shape."""


def group_key(f: Finding) -> str:
    """Identifies findings as "the same kind of thing" across scans:
    same detector, same file, same object, same flagged fragment. Not
    unique per finding -- see the module docstring for why that's
    intentional."""
    base = "\x1f".join((f.detector, f.source_file, f.object_name, f.snippet))
    return hashlib.sha1(base.encode()).hexdigest()[:12]


def save_baseline(findings: list[Finding], path: Path) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "findings": [
            {"group_key": group_key(f), **dataclasses.asdict(f)} for f in findings
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_baseline(path: Path) -> list[dict]:
    """Raw finding records from a file written by save_baseline(), each
    carrying its 'group_key'."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BaselineLoadError(f"{path}: не удалось прочитать ({exc})") from exc
    except UnicodeDecodeError as exc:
        raise BaselineLoadError(f"{path}: не в кодировке UTF-8 ({exc})") from exc
    except json.JSONDecodeError as exc:
        raise BaselineLoadError(f"{path}: не похоже на JSON ({exc})") from exc

    if not isinstance(raw, dict) or not isinstance(raw.get("findings"), list):
        raise BaselineLoadError(
            f"{path}: не похоже на baseline-файл ora2pg-gap-report (нет списка 'findings')"
        )
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise BaselineLoadError(
            f"{path}: schema_version={raw.get('schema_version')!r}, эта версия инструмента "
            f"ожидает {SCHEMA_VERSION} — пересохраните baseline через --save текущей версией"
        )
    for rec in raw["findings"]:
        if not isinstance(rec, dict) or "group_key" not in rec:
            raise BaselineLoadError(f"{path}: запись находки без 'group_key'")
    return raw["findings"]


@dataclasses.dataclass(frozen=True)
class BaselineDiff:
    new: list[Finding]
    resolved: list[dict]
    unchanged_count: int


def diff_against_baseline(findings: list[Finding], baseline: list[dict]) -> BaselineDiff:
    """Compares by group counts, not by matching individual records to
    each other -- see the module docstring for why. For a group present
    N times in the baseline and M times now: min(N, M) count as
    unchanged, any excess in the baseline is resolved, any excess now is
    new. Which specific finding ends up in `new`/`resolved` for a group
    with more than one instance is arbitrary (list order) when they're
    genuinely indistinguishable; the counts themselves are always
    correct regardless."""
    baseline_groups: dict[str, list[dict]] = {}
    for rec in baseline:
        baseline_groups.setdefault(rec["group_key"], []).append(rec)

    current_groups: dict[str, list[Finding]] = {}
    for f in findings:
        current_groups.setdefault(group_key(f), []).append(f)

    new: list[Finding] = []
    resolved: list[dict] = []
    unchanged_count = 0

    for key in set(baseline_groups) | set(current_groups):
        base_list = baseline_groups.get(key, [])
        current_list = current_groups.get(key, [])
        matched = min(len(base_list), len(current_list))
        unchanged_count += matched
        new.extend(current_list[matched:])
        resolved.extend(base_list[matched:])

    return BaselineDiff(new=new, resolved=resolved, unchanged_count=unchanged_count)
