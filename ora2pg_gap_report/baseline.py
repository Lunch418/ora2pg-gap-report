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

from . import i18n
from .atomic_write import write_text_atomic
from .gap_registry import gap_metadata
from .models import Finding

SCHEMA_VERSION = 3

# Deliberately narrower than schemas/baseline.schema.json's full required
# list: just the two fields this module and verification.py actually
# dereference without a .get() fallback ('detector' is the one that used
# to surface as a raw KeyError from verify_against_baseline). Not
# gap_number/failure_stage -- test_load_baseline_tolerates_a_snapshot_
# saved_before_gap_metadata_existed is an intentional backward-compat
# guarantee for --save snapshots written before those fields existed,
# and requiring the schema's full list here would break it.
_REQUIRED_FINDING_FIELDS = frozenset({"group_key", "detector"})


class BaselineLoadError(Exception):
    """A --baseline file couldn't be read or isn't in the expected shape."""


def _normalized_source_file(source_file: str) -> str:
    """The form of `source_file` that group_key() actually hashes -- not
    the literal argv spelling, which is unstable in exactly the way a
    --save/--baseline pair needs to agree: 'pkg.sql' and '$PWD/pkg.sql'
    are the same file scanned the same session, but resolve() them both
    and take the result relative to the current directory and they
    collapse to the identical string 'pkg.sql', same as a redundant
    './', a trailing slash, or a '..' segment would. as_posix() keeps the
    separator consistent within whichever OS this actually runs on
    (pathlib already picks WindowsPath vs PosixPath per-platform) -- it
    does not make a baseline saved on Windows and verified on Linux
    agree, which would need the path's original OS recorded alongside
    it, not just a different string form. Falling back to the resolved
    absolute path for anything outside the cwd keeps every case
    unambiguous without needing a schema field to record what root it
    was relative to -- the common workflow this exists for (re-scan the
    same checkout from the same place you saved the baseline from,
    whether that's a developer's shell or a CI job) already shares a cwd
    between the two runs, which is all this normalization needs to
    agree."""
    resolved = Path(source_file).resolve()
    try:
        return resolved.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return resolved.as_posix()


def group_key(f: Finding) -> str:
    """Identifies findings as "the same kind of thing" across scans:
    same detector, same file, same object, same flagged fragment. Not
    unique per finding -- see the module docstring for why that's
    intentional. `source_file` is normalized before hashing (see
    _normalized_source_file) so two scans of the same file from the same
    place agree regardless of how the path was spelled on the command
    line."""
    base = "\x1f".join((f.detector, _normalized_source_file(f.source_file), f.object_name, f.snippet))
    return hashlib.sha1(base.encode()).hexdigest()[:12]


def save_baseline(findings: list[Finding], path: Path) -> None:
    findings_payload = []
    for f in findings:
        gap_number, failure_stage = gap_metadata(f.detector)
        findings_payload.append(
            {
                "group_key": group_key(f),
                **dataclasses.asdict(f),
                "gap_number": gap_number,
                "failure_stage": failure_stage,
            }
        )
    payload = {"schema_version": SCHEMA_VERSION, "findings": findings_payload}
    write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def load_baseline(path: Path, lang: str = "ru") -> list[dict]:
    """Raw finding records from a file written by save_baseline(), each
    carrying its 'group_key'."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BaselineLoadError(i18n.t(lang, "baseline_unreadable", path=path, exc=exc)) from exc
    except UnicodeDecodeError as exc:
        raise BaselineLoadError(i18n.t(lang, "baseline_not_utf8", path=path, exc=exc)) from exc
    except json.JSONDecodeError as exc:
        raise BaselineLoadError(i18n.t(lang, "baseline_not_json", path=path, exc=exc)) from exc

    if not isinstance(raw, dict) or not isinstance(raw.get("findings"), list):
        raise BaselineLoadError(i18n.t(lang, "baseline_no_findings_key", path=path))
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise BaselineLoadError(
            i18n.t(
                lang,
                "baseline_schema_mismatch",
                path=path,
                schema_version=raw.get("schema_version"),
                expected=SCHEMA_VERSION,
            )
        )
    # The full set schemas/baseline.schema.json requires per finding, not
    # just 'group_key' -- verify_against_baseline() (verification.py)
    # reads rec["detector"] unconditionally, and a baseline that passed
    # this check but was missing it used to surface as a raw KeyError
    # instead of the same clean "this file is broken" message every other
    # malformed-baseline case gets.
    for rec in raw["findings"]:
        if not isinstance(rec, dict):
            raise BaselineLoadError(i18n.t(lang, "baseline_missing_field", path=path, field="group_key"))
        missing = _REQUIRED_FINDING_FIELDS - rec.keys()
        if missing:
            raise BaselineLoadError(
                i18n.t(lang, "baseline_missing_field", path=path, field=", ".join(sorted(missing)))
            )
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
