"""Baseline snapshots — track findings across repeated scans of a schema
that keeps changing during a migration project (fix some gaps, re-scan,
see what's left).

A finding's identity across two scans can't be its line number: lines
shift on any unrelated edit anywhere in the file, not just edits to the
flagged construct itself. It also can't be its position in the findings
list, since sort order depends on what else was found in that scan.
Instead each finding is fingerprinted by what actually identifies *what*
was found, not *where* on the page: which detector found it, which file,
which object, and the flagged fragment (snippet). Two genuinely distinct
findings that happen to share all four (e.g. the same DBMS_LOB call
appearing twice in one package body) are disambiguated by their order of
appearance among findings sharing that same base — stable as long as the
two occurrences don't swap relative order between scans, the same
assumption cli.py's own _sort_findings() already makes about severity/
object_name/line ties.
"""

import dataclasses
import hashlib
import json
from pathlib import Path

from .models import Finding

SCHEMA_VERSION = 1


class BaselineLoadError(Exception):
    """A --baseline file couldn't be read or isn't in the expected shape."""


def _fingerprint_base(f: Finding) -> str:
    return "\x1f".join((f.detector, f.source_file, f.object_name, f.snippet))


def compute_fingerprints(findings: list[Finding]) -> list[str]:
    """One fingerprint per finding, same order as `findings`."""
    occurrence_of: dict[str, int] = {}
    fingerprints = []
    for f in findings:
        base = _fingerprint_base(f)
        occurrence = occurrence_of.get(base, 0)
        occurrence_of[base] = occurrence + 1
        digest = hashlib.sha1(f"{base}\x1f{occurrence}".encode()).hexdigest()[:12]
        fingerprints.append(digest)
    return fingerprints


def save_baseline(findings: list[Finding], path: Path) -> None:
    fingerprints = compute_fingerprints(findings)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "findings": [
            {"fingerprint": fp, **dataclasses.asdict(f)} for fp, f in zip(fingerprints, findings)
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_baseline(path: Path) -> dict[str, dict]:
    """{fingerprint: saved finding record}, from a file written by
    save_baseline()."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BaselineLoadError(f"{path}: не удалось прочитать ({exc})") from exc
    except json.JSONDecodeError as exc:
        raise BaselineLoadError(f"{path}: не похоже на JSON ({exc})") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("findings"), list):
        raise BaselineLoadError(
            f"{path}: не похоже на baseline-файл ora2pg-gap-report (нет списка 'findings')"
        )
    try:
        return {rec["fingerprint"]: rec for rec in raw["findings"]}
    except (KeyError, TypeError) as exc:
        raise BaselineLoadError(f"{path}: запись находки без 'fingerprint' ({exc})") from exc


@dataclasses.dataclass(frozen=True)
class BaselineDiff:
    new: list[Finding]
    resolved: list[dict]
    unchanged_count: int


def diff_against_baseline(findings: list[Finding], baseline: dict[str, dict]) -> BaselineDiff:
    fingerprints = compute_fingerprints(findings)
    current_fingerprints = set(fingerprints)
    new = [f for f, fp in zip(findings, fingerprints) if fp not in baseline]
    resolved = [rec for fp, rec in baseline.items() if fp not in current_fingerprints]
    return BaselineDiff(new=new, resolved=resolved, unchanged_count=len(findings) - len(new))
