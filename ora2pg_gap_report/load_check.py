"""--load-check: loads ora2pg's generated PostgreSQL files into a real,
throwaway PostgreSQL and ties every statement that fails to a GAP-NNN.

Every other mode of this tool is static: it reads text and says what
*may* break. This one asks PostgreSQL itself. It is the step a migration
engineer does by hand anyway -- run the generated files through psql and
read the errors -- with the part that takes the time done for them: which
known gap each error is, whether --fix repairs it, and which errors are
only the echo of an earlier failure.

## How the database is kept clean

Everything runs in ONE transaction that is rolled back at the end, with
psql's ON_ERROR_ROLLBACK on, so a failed statement is rolled back to a
savepoint and the rest keep loading (a plain transaction would refuse
every statement after the first error). Before the files are fed to psql
their own transaction control is blanked out (pg_script.sanitize), so no
COMMIT in a file can end the check's transaction early. If psql dies
halfway, the server rolls the open transaction back when the connection
drops. Nothing is ever committed.

Two targets:

- `docker[:IMAGE]` -- a fresh container (postgres:16-alpine by default,
  the version every gap in the registry was confirmed against), removed
  afterwards. Needs docker, nothing else; psql runs inside the container.
- a libpq connection string or URI -- an existing server, through the
  local `psql`. Point it at a scratch database: nothing is committed, but
  DDL takes locks that are held until the final ROLLBACK.

## What "loaded" means

`check_function_bodies` is forced on (ora2pg turns it off in every file
it writes), so PL/pgSQL bodies are parsed -- which is where most of the
registry's "fails at compile time" gaps surface. Nothing is executed: a
statement that loads may still behave differently from Oracle at run
time, and the report says so.
"""

from __future__ import annotations

import dataclasses
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from collections.abc import Sequence
from pathlib import Path

from .autofix import FIXER_DETECTOR, FIXER_SQLSTATE, FIXERS_BY_DIALECT
from .core import expand_paths, scan_source
from .gap_registry import gap_by_detector
from .models import Finding
from .pg_script import Neutralised, ParsedScript, Statement, parse_script, sanitize

DEFAULT_DOCKER_IMAGE = "postgres:16-alpine"

# Categories, in the order the report shows them: what to act on first.
FIXABLE = "fixable"  # a --fix fixer repairs the statement
GAP = "gap"  # a registered gap's construct sits in the failing statement
UNKNOWN = "unknown"  # fails, and matches nothing this tool knows about
DEPENDENCY = "dependency"  # refers to an object that does not exist
ENVIRONMENT = "environment"  # the check itself could not run it (privileges, transaction rules)
CATEGORIES = (FIXABLE, GAP, UNKNOWN, DEPENDENCY, ENVIRONMENT)
# Categories that mean "this output does not load" -- exit code 1.
FAILING_CATEGORIES = frozenset({FIXABLE, GAP, UNKNOWN, DEPENDENCY})

# "An object this statement refers to doesn't exist." Almost always the
# echo of an earlier statement that failed (the table whose CREATE broke)
# or an object that lives outside the loaded files. Reported apart from
# the real causes, so the list starts with what to fix.
_DEPENDENCY_STATES = frozenset(
    {
        "42P01",  # undefined_table
        "42704",  # undefined_object (a type, usually)
        "3F000",  # invalid_schema_name
        "42883",  # undefined_function
    }
)
# The statement could not be checked here, which says nothing about the
# migration: it cannot run inside a transaction (CREATE INDEX
# CONCURRENTLY, CREATE DATABASE), ends one (COMMIT inside a DO block),
# was refused by the target server's rules, or timed out.
_ENVIRONMENT_STATES = frozenset(
    {
        "25001",  # active_sql_transaction: cannot run inside a transaction block
        "2D000",  # invalid_transaction_termination
        "42501",  # insufficient_privilege
        "58P01",  # undefined_file: an extension not installed on the server
        "57014",  # query_canceled: statement_timeout
        "55P03",  # lock_not_available: lock_timeout
    }
)

_REMOTE_DIR = "/tmp/ora2pg-gap-report-load-check"
_MARK = "@@ora2pg-gap-report"


class LoadCheckError(Exception):
    """The check itself could not run (no docker, no psql, no connection).
    Carries an i18n key and its arguments; cli.py renders it."""

    def __init__(self, key: str, **kwargs: object) -> None:
        super().__init__(key)
        self.key = key
        self.kwargs = kwargs


@dataclasses.dataclass(frozen=True)
class Target:
    kind: str  # "docker" | "dsn"
    value: str  # the image, or the connection string

    def describe(self) -> str:
        if self.kind == "docker":
            return f"docker {self.value}"
        return _redact_dsn(self.value)


def parse_target(raw: str) -> Target:
    """`docker`, `docker:IMAGE`, or anything else as a libpq connection
    string / URI."""
    text = raw.strip()
    if text.lower() == "docker":
        return Target("docker", DEFAULT_DOCKER_IMAGE)
    if text.lower().startswith("docker:") and len(text) > len("docker:"):
        return Target("docker", text[len("docker:") :])
    return Target("dsn", text)


def _redact_dsn(dsn: str) -> str:
    """The connection string without its password, for the report."""
    redacted = re.sub(r"(://[^:/@]*:)[^@]*@", r"\1***@", dsn)
    return re.sub(r"(password\s*=\s*)(?:'[^']*'|\S+)", r"\1***", redacted, flags=re.IGNORECASE)


@dataclasses.dataclass(frozen=True)
class LoadError:
    file: str
    line: int  # best known line of the error itself
    statement_line: int  # first line of the failing statement
    sqlstate: str
    message: str
    detail: str | None
    hint: str | None
    context: str | None
    category: str
    detector: str | None = None
    gap_number: str | None = None


@dataclasses.dataclass(frozen=True)
class SkippedFile:
    file: str
    reason: str  # "unreadable" | "unterminated"
    line: int | None = None
    detail: str | None = None


@dataclasses.dataclass(frozen=True)
class LoadCheckResult:
    target: str
    server_version: str | None
    files: tuple[str, ...]
    statements: int
    errors: tuple[LoadError, ...]
    neutralised: tuple[tuple[str, Neutralised], ...]
    skipped_files: tuple[SkippedFile, ...]
    elapsed_seconds: float

    @property
    def failed(self) -> bool:
        return any(e.category in FAILING_CATEGORIES for e in self.errors)


# --- choosing and ordering the files ---------------------------------------

# ora2pg's own object types, in an order where each one's dependencies
# load first: types and sequences before the tables that use them, tables
# before views, indexes, constraints and foreign keys, grants last.
_TYPE_RANK: dict[str, int] = {}
for _rank, _names in enumerate(
    (
        ("TYPE", "TYPES", "DOMAIN", "DOMAINS"),
        ("SEQUENCE", "SEQUENCES"),
        ("TABLE", "TABLES"),
        ("PARTITION", "PARTITIONS"),
        # data, after the tables it fills and before the indexes and
        # constraints that would slow the load or reject half-loaded rows
        ("COPY", "INSERT", "DATA"),
        ("FDW", "FOREIGN"),
        ("VIEW", "VIEWS", "SYNONYM", "SYNONYMS"),
        ("MVIEW", "MVIEWS", "MATERIALIZED"),
        ("FUNCTION", "FUNCTIONS"),
        ("PROCEDURE", "PROCEDURES"),
        ("PACKAGE", "PACKAGES"),
        ("TRIGGER", "TRIGGERS"),
        ("INDEX", "INDEXES"),
        ("CONSTRAINT", "CONSTRAINTS"),
        ("FKEY", "FKEYS"),
        ("GRANT", "GRANTS"),
    )
):
    for _name in _names:
        _TYPE_RANK[_name] = _rank
_UNKNOWN_RANK = _TYPE_RANK["FUNCTION"]


def _type_rank(path: Path, root: Path) -> int:
    """Where a file goes in the load order, from the first ora2pg type
    name in its file name, else in its directories (closest first)."""
    try:
        parents = list(path.relative_to(root).parent.parts)
    except ValueError:
        parents = []
    for part in [path.stem, *reversed(parents)]:
        for token in re.split(r"[^A-Za-z]+", part):
            rank = _TYPE_RANK.get(token.upper())
            if rank is not None:
                return rank
    return _UNKNOWN_RANK


def order_files(paths: Sequence[Path]) -> tuple[list[Path], list[Path]]:
    """The files to load, in load order, and the directories that held
    none. Files named on the command line keep the order they were given
    in; a directory's files are put in ora2pg's type order (see
    _TYPE_RANK), then by name."""
    ordered: list[Path] = []
    empty_dirs: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        found, empty = expand_paths([path])
        empty_dirs.extend(empty)
        if path.is_dir():
            found.sort(key=lambda p: (_type_rank(p, path), str(p)))
        for p in found:
            resolved = p.resolve()
            if resolved not in seen:
                seen.add(resolved)
                ordered.append(p)
    return ordered, empty_dirs


# --- preparing the files ---------------------------------------------------


@dataclasses.dataclass
class _PreparedFile:
    path: Path
    script_name: str  # the sanitized copy's file name
    source: str  # decoded with surrogateescape
    parsed: ParsedScript


def _prepare(files: Sequence[Path], workdir: Path) -> tuple[list[_PreparedFile], list[SkippedFile], list[tuple[str, Neutralised]]]:
    prepared: list[_PreparedFile] = []
    skipped: list[SkippedFile] = []
    neutralised: list[tuple[str, Neutralised]] = []
    for path in files:
        try:
            raw = path.read_bytes()
        except OSError as exc:
            skipped.append(SkippedFile(str(path), "unreadable", detail=str(exc)))
            continue
        # surrogateescape both ways: the copy psql reads has exactly the
        # file's own bytes (cp1251 comments included) wherever nothing
        # was blanked.
        source = raw.decode("utf-8", errors="surrogateescape")
        parsed = parse_script(source)
        if parsed.unterminated is not None:
            # psql would carry the open quote over into the next file and
            # swallow it. Better to say so than to report nonsense.
            skipped.append(SkippedFile(str(path), "unterminated", parsed.unterminated_line, parsed.unterminated))
            continue
        clean, removed = sanitize(source, parsed)
        name = f"{len(prepared) + 1:04d}.sql"
        (workdir / name).write_bytes(clean.encode("utf-8", errors="surrogateescape"))
        prepared.append(_PreparedFile(path, name, source, parsed))
        neutralised.extend((str(path), r) for r in removed)
    return prepared, skipped, neutralised


def _driver_script(script_dir: str, prepared: Sequence[_PreparedFile]) -> str:
    lines = [
        "\\set VERBOSITY verbose",
        "\\set ON_ERROR_STOP 0",
        "\\set ON_ERROR_ROLLBACK on",
        "\\pset pager off",
        f"\\echo {_MARK}:server:" + " :SERVER_VERSION_NAME",
        # English messages where the server allows it (superuser only);
        # SQLSTATE codes are what the parsing relies on either way.
        "SET lc_messages TO 'C';",
        "SET client_min_messages TO warning;",
        "BEGIN;",
        "SET LOCAL check_function_bodies = on;",
        "SET LOCAL lock_timeout = '5s';",
        "SET LOCAL statement_timeout = '5min';",
    ]
    for p in prepared:
        lines.append(f"\\echo {_MARK}:file:{p.script_name}")
        # psql sends whatever is left in its buffer when an \\i'd file
        # ends, so an unterminated last statement is not glued to the
        # next file's first line.
        lines.append(f"\\i '{script_dir}/{p.script_name}'")
    lines.append("ROLLBACK;")
    lines.append(f"\\echo {_MARK}:done")
    return "\n".join(lines) + "\n"


# --- running psql ----------------------------------------------------------


def _run(cmd: Sequence[str], *, env: dict[str, str] | None = None, timeout: float | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(list(cmd), capture_output=True, env=env, timeout=timeout, check=False)


def _psql_env() -> dict[str, str]:
    """The environment for a local psql: English client-side messages
    (`LINE n:`, `DETAIL:` come from libpq, in the client's language)
    without touching the locale's character set."""
    env = dict(os.environ)
    lc_all = env.pop("LC_ALL", None)
    if lc_all:
        env.setdefault("LC_CTYPE", lc_all)
    env.pop("LANGUAGE", None)
    env["LC_MESSAGES"] = "C"
    env.setdefault("PGAPPNAME", "ora2pg-gap-report")
    env.setdefault("PGCONNECT_TIMEOUT", "10")
    return env


def _decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _run_dsn(dsn: str, workdir: Path, psql_bin: str) -> tuple[str, str]:
    driver = workdir / "driver.sql"
    try:
        proc = _run([psql_bin, "-X", "-q", "-d", dsn, "-f", str(driver)], env=_psql_env())
    except FileNotFoundError as exc:
        raise LoadCheckError("load_check_no_psql", psql=psql_bin) from exc
    stdout, stderr = _decode(proc.stdout), _decode(proc.stderr)
    if f"{_MARK}:server:" not in stdout:
        raise LoadCheckError("load_check_connect_failed", detail=stderr.strip() or f"exit {proc.returncode}")
    return stdout, stderr


def _docker(docker_bin: str, *args: str, timeout: float | None = None) -> subprocess.CompletedProcess[bytes]:
    try:
        return _run([docker_bin, *args], timeout=timeout)
    except FileNotFoundError as exc:
        raise LoadCheckError("load_check_no_docker", docker=docker_bin) from exc


def _run_docker(image: str, workdir: Path, docker_bin: str, ready_timeout: float = 120.0) -> tuple[str, str]:
    name = f"ora2pg-gap-load-check-{uuid.uuid4().hex[:12]}"
    # Trust auth inside a container that publishes no port: nothing
    # outside the container can reach the server at all.
    started = _docker(
        docker_bin, "run", "-d", "--rm", "--name", name, "-e", "POSTGRES_HOST_AUTH_METHOD=trust", image
    )
    if started.returncode != 0:
        raise LoadCheckError("load_check_docker_failed", image=image, detail=_decode(started.stderr).strip())
    try:
        # Over TCP, not the socket: the image's entrypoint first runs a
        # temporary socket-only server for initialisation and restarts it,
        # so only a TCP answer means the real server is up.
        deadline = time.monotonic() + ready_timeout
        while True:
            ready = _docker(docker_bin, "exec", name, "pg_isready", "-q", "-h", "127.0.0.1", "-U", "postgres", timeout=30)
            if ready.returncode == 0:
                break
            if time.monotonic() > deadline:
                logs = _docker(docker_bin, "logs", "--tail", "20", name, timeout=30)
                raise LoadCheckError(
                    "load_check_docker_not_ready",
                    image=image,
                    detail=(_decode(logs.stdout) + _decode(logs.stderr)).strip(),
                )
            time.sleep(0.5)
        copied = _docker(docker_bin, "cp", f"{workdir}{os.sep}.", f"{name}:{_REMOTE_DIR}", timeout=300)
        if copied.returncode != 0:
            raise LoadCheckError("load_check_docker_failed", image=image, detail=_decode(copied.stderr).strip())
        proc = _docker(
            docker_bin,
            "exec",
            "-e",
            "LC_MESSAGES=C",
            name,
            "psql", "-X", "-q", "-h", "127.0.0.1", "-U", "postgres", "-f", f"{_REMOTE_DIR}/driver.sql",
        )
        stdout, stderr = _decode(proc.stdout), _decode(proc.stderr)
        if f"{_MARK}:server:" not in stdout:
            raise LoadCheckError("load_check_connect_failed", detail=stderr.strip() or f"exit {proc.returncode}")
        return stdout, stderr
    finally:
        _docker(docker_bin, "rm", "-f", name, timeout=60)


# --- reading psql's output -------------------------------------------------


@dataclasses.dataclass
class _RawError:
    script: str
    end_line: int
    sqlstate: str
    message: str
    position_line: int | None = None  # the `LINE n:` number, statement-relative
    position_text: str | None = None
    detail: str | None = None
    hint: str | None = None
    context: str | None = None


# `psql:<file>:<line>: ERROR:  42601: message`. The severity word is the
# server's and can be translated; the SQLSTATE cannot, so it is what
# matters. Warnings (class 01) are not errors and are dropped later.
_ERROR_RE = re.compile(r"^psql:(?P<path>.+?):(?P<line>\d+): \S+:\s+(?P<code>[0-9A-Z]{5}): (?P<msg>.*)$")
_LINE_RE = re.compile(r"^(?:LINE|СТРОКА) (?P<n>\d+): (?P<text>.*)$")
_FIELD_RE = re.compile(r"^(?P<key>DETAIL|HINT|CONTEXT|ПОДРОБНОСТИ|ПОДСКАЗКА|КОНТЕКСТ):\s+(?P<text>.*)$")
_FIELD_KEYS = {
    "DETAIL": "detail",
    "ПОДРОБНОСТИ": "detail",
    "HINT": "hint",
    "ПОДСКАЗКА": "hint",
    "CONTEXT": "context",
    "КОНТЕКСТ": "context",
}


def parse_psql_errors(stderr: str, script_names: Sequence[str]) -> list[_RawError]:
    """The errors psql reported against the sanitized copies, in order.
    Errors from the driver script itself (the lc_messages SET a
    non-superuser is refused) are not the user's and are left out."""
    known = set(script_names)
    errors: list[_RawError] = []
    current: _RawError | None = None
    for raw_line in stderr.splitlines():
        m = _ERROR_RE.match(raw_line)
        if m is not None:
            current = None
            script = m.group("path").replace("\\", "/").rsplit("/", 1)[-1]
            if script in known and not m.group("code").startswith(("00", "01", "02")):
                current = _RawError(script, int(m.group("line")), m.group("code"), m.group("msg").strip())
                errors.append(current)
            continue
        if current is None:
            continue
        lm = _LINE_RE.match(raw_line)
        if lm is not None and current.position_line is None:
            current.position_line = int(lm.group("n"))
            current.position_text = lm.group("text")
            continue
        fm = _FIELD_RE.match(raw_line)
        if fm is not None:
            key = _FIELD_KEYS[fm.group("key")]
            if getattr(current, key) is None:
                setattr(current, key, fm.group("text").strip())
    return errors


def server_version(stdout: str) -> str | None:
    for line in stdout.splitlines():
        if line.startswith(f"{_MARK}:server:"):
            value = line[len(f"{_MARK}:server:") :].strip()
            return value or None
    return None


# --- tying errors to statements and gaps ------------------------------------


def _statement_for(parsed: ParsedScript, end_line: int, taken: set[int]) -> Statement | None:
    """The statement psql reported on `end_line` (the line its semicolon is
    on). Several can end on one line; each error claims the next one not
    already claimed."""
    candidates = [k for k, s in enumerate(parsed.statements) if s.end_line == end_line]
    for k in candidates:
        if k not in taken:
            taken.add(k)
            return parsed.statements[k]
    if candidates:
        return parsed.statements[candidates[-1]]
    # No statement ends there (a tail psql sent at end of file): the last
    # one that starts at or before it.
    before = [s for s in parsed.statements if s.start_line <= end_line]
    return before[-1] if before else None


def _error_line(source: str, statement: Statement, raw: _RawError) -> int:
    """The line the error points at. psql's `LINE n:` counts from the
    statement's first line; the text after it confirms which line that is
    when comments or blank lines make the count drift."""
    if raw.position_line is None:
        return statement.start_line
    guess = statement.start_line + raw.position_line - 1
    fragment = (raw.position_text or "").strip()
    fragment = fragment.removeprefix("...").removesuffix("...").strip()
    if not fragment:
        return guess
    lines = source[statement.start : statement.end].split("\n")
    matches = [statement.start_line + k for k, text in enumerate(lines) if fragment in text]
    if not matches:
        return guess
    return min(matches, key=lambda line: abs(line - guess))


def _fixer_detector(statement_text: str, dialect: str, sqlstate: str = "") -> str | None:
    fixers = FIXERS_BY_DIALECT.get(dialect, ())
    # A fix that answers exactly this SQLSTATE explains the error better
    # than one that merely changes something else in the statement.
    ordered = sorted(fixers, key=lambda f: FIXER_SQLSTATE.get(f) != sqlstate)
    for fixer in ordered:
        if FIXER_SQLSTATE.get(fixer, sqlstate) != sqlstate:
            continue
        _, applied = fixer(statement_text)
        if applied:
            return FIXER_DETECTOR.get(fixer)
    return None


# How far above the error line a construct may start and still be what
# PostgreSQL choked on: a declaration like `TYPE t IS TABLE OF ...` can span
# a couple of lines before the token the parser stops at.
_LINES_BEFORE = 3


# A finding that explains only one kind of error. A schema-qualified CREATE
# (GAP-124) is the reason for 'schema "hr" does not exist' on its line, not
# for whatever else that statement may fail on.
_DETECTOR_SQLSTATES: dict[str, frozenset[str]] = {
    "schema_qualified_name": frozenset({"3F000"}),
}


def _gap_finding(findings: Sequence[Finding], statement: Statement, line: int, sqlstate: str) -> Finding | None:
    """The finding that explains an error on `line`, or None.

    A syntax error stops at the first token the parser cannot take, so its
    cause is on that line or just above it -- never further down, and not
    anywhere in a long routine that happens to contain some flagged
    construct. An error about a missing object ("relation ... does not
    exist") is a gap only when the gap's construct is on that very line;
    otherwise it is a missing table or type, and is reported as such. Both
    rules came from loading real ora2pg output for OraOpenSource Logger,
    where a $IF further down a procedure claimed its unrelated errors."""
    inside = [
        f
        for f in findings
        if statement.start_line <= f.line <= statement.end_line
        and sqlstate in _DETECTOR_SQLSTATES.get(f.detector, frozenset({sqlstate}))
    ]
    exact = [f for f in inside if f.line == line]
    if exact:
        return exact[0]
    if sqlstate in _DEPENDENCY_STATES:
        return None
    near = [f for f in inside if line - _LINES_BEFORE <= f.line < line]
    return near[-1] if near else None


def _load_error(
    raw: _RawError, file: str, line: int, statement_line: int, category: str, detector: str | None = None
) -> LoadError:
    gap = gap_by_detector(detector) if detector is not None else None
    return LoadError(
        file=file,
        line=line,
        statement_line=statement_line,
        sqlstate=raw.sqlstate,
        message=raw.message,
        detail=raw.detail,
        hint=raw.hint,
        context=raw.context,
        category=category,
        detector=detector,
        gap_number=gap.number if gap is not None else None,
    )


def _classify(
    raw: _RawError, prepared: _PreparedFile, findings: Sequence[Finding], taken: set[int], dialect: str
) -> LoadError:
    file = str(prepared.path)
    statement = _statement_for(prepared.parsed, raw.end_line, taken)
    if statement is None:
        category = ENVIRONMENT if raw.sqlstate in _ENVIRONMENT_STATES else UNKNOWN
        return _load_error(raw, file, raw.end_line, raw.end_line, category)

    line = _error_line(prepared.source, statement, raw)
    if raw.sqlstate in _ENVIRONMENT_STATES:
        return _load_error(raw, file, line, statement.start_line, ENVIRONMENT)

    fixer_detector = _fixer_detector(prepared.source[statement.start : statement.end], dialect, raw.sqlstate)
    if fixer_detector is not None:
        return _load_error(raw, file, line, statement.start_line, FIXABLE, fixer_detector)

    finding = _gap_finding(findings, statement, line, raw.sqlstate)
    if finding is not None:
        return _load_error(raw, file, line, statement.start_line, GAP, finding.detector)

    signature = _output_signature(prepared.source, statement, line, raw.message)
    if signature is not None:
        return _load_error(raw, file, line, statement.start_line, GAP, signature)

    category = DEPENDENCY if raw.sqlstate in _DEPENDENCY_STATES or _missing_anchor(raw) else UNKNOWN
    return _load_error(raw, file, line, statement.start_line, category)


# PL/pgSQL reports `x tab.col%TYPE` whose table does not exist as a syntax
# error ('invalid type name "employees.salary%TYPE"'), not as a missing
# relation -- but it is the same thing: an object outside what was loaded.
_ANCHORED_TYPE_RE = re.compile(r'^invalid type name ".*%(?:ROW)?TYPE"$', re.IGNORECASE)


def _missing_anchor(raw: _RawError) -> bool:
    return raw.sqlstate == "42601" and bool(raw.context and _ANCHORED_TYPE_RE.match(raw.context))


# What some gaps leave in ora2pg's *output*. The detectors look for the
# Oracle construct, and for these gaps it does not survive conversion (they
# are not_verifiable), so a load error caused by one cannot be tied to it by
# re-running the detector. The footprint ora2pg leaves instead can be
# recognised on the failing line or statement. Each one is the exact shape
# recorded in the gap's research doc.
_REFCURSOR_TYPE_RE = re.compile(r"\bCREATE\s+OR\s+REPLACE\s+TYPE\s+\S+\s+AS\s+REFCURSOR\b", re.IGNORECASE)
# current_setting('pkg.c')::varchar(30) followed straight by a name or by
# another current_setting( -- two operands spliced with no operator.
_SPLICED_CONSTANT_RE = re.compile(
    r"current_setting\('[^']*'\)::[A-Za-z_]\w*\b(?:\s*\(\s*\d+(?:\s*,\s*\d+)?\s*\))?(?:current_setting\(|[A-Za-z_])",
    re.IGNORECASE,
)
# A bare procedure call statement: pkg.proc(...); or pkg.proc; -- what a
# trigger keeps (GAP-117). Inside a package, GAP-116's repeat comes out as
# pkg.proc(); with the empty parentheses ora2pg adds, and only that shape
# is its footprint: a bare call with arguments there is something else (a
# package outside the run, OWA's htp.p).
_BARE_CALL_RE = re.compile(r"^\s*[A-Za-z_]\w*\s*\.\s*[A-Za-z_]\w*\s*(?:\(.*\))?\s*;\s*$")
_EMPTY_PARENS_CALL_RE = re.compile(r"^\s*[A-Za-z_]\w*\s*\.\s*[A-Za-z_]\w*\s*\(\s*\)\s*;\s*$")
_TRIGGER_FUNCTION_RE = re.compile(r"\bRETURNS\s+trigger\b", re.IGNORECASE)


# GAP-119: the name PostgreSQL could not resolve sits in a parameter's
# DEFAULT -- "column "g_os" does not exist" for a bare name, "missing
# FROM-clause entry for table "pkg"" for pkg.g_os.
_UNRESOLVED_NAME_RE = re.compile(r'^(?:column|missing FROM-clause entry for table) "([^"]+)"')


# GAP-035: what is left of a $IF ... $THEN ... $END after ora2pg -- the
# directives and $$inquiry names, with the $IF itself often eaten.
_CONDITIONAL_COMPILATION_RE = re.compile(
    r"(?<![\w$])\$(?:if|then|elsif|else|end|error)\b(?!\$)|(?<![\w$])\$\$[A-Za-z_]\w*\b(?!\$)", re.IGNORECASE
)
# GAP-003: a collection method on a package collection, which GAP-036's
# emulation turned into current_setting(...)::type.DELETE.
_COLLECTION_METHOD_RE = re.compile(
    r"current_setting\('[^']*'\)::\w+\.(?:DELETE|COUNT|EXTEND|TRIM|FIRST|LAST|EXISTS|PRIOR|NEXT|LIMIT)\b",
    re.IGNORECASE,
)
# GAP-120: %TYPE/%ROWTYPE copied into a package type's CREATE TYPE/DOMAIN.
_ANCHORED_TYPE_DDL_RE = re.compile(r"^\s*CREATE\s+(?:TYPE|DOMAIN)\b[^;]*%(?:ROW)?TYPE\b", re.IGNORECASE)
# GAP-121: a type the same file creates in a package schema, named bare.
_MISSING_TYPE_RE = re.compile(r'^type "?([A-Za-z_][\w$#]*)"? does not exist$', re.IGNORECASE)
# GAP-122: a supplied package's procedure called bare.
_SUPPLIED_CALL_RE = re.compile(
    r"^\s*(?:DBMS_\w*|UTL_\w*|HTP|OWA(?:_\w*)?|APEX_\w*|CTX_\w*)\s*\.\s*[A-Za-z_]\w*\s*(?:\(|;)", re.IGNORECASE
)


def _created_in_a_schema(source: str, name: str) -> bool:
    return bool(re.search(rf"\bCREATE\s+(?:TYPE|DOMAIN)\s+\w+\.{re.escape(name)}\b", source, re.IGNORECASE))


def _in_a_default(statement_text: str, name: str) -> bool:
    return bool(re.search(rf"\bDEFAULT\s+{re.escape(name)}\b", statement_text, re.IGNORECASE))


def _output_signature(source: str, statement: Statement, line: int, message: str = "") -> str | None:
    """The detector whose gap left the footprint the failing line shows, or
    None."""
    text = source[statement.start : statement.end]
    lines = source.split("\n")
    at = lines[line - 1] if 0 < line <= len(lines) else ""
    if _REFCURSOR_TYPE_RE.search(text):
        return "ref_cursor_type"
    if _ANCHORED_TYPE_DDL_RE.search(text):
        return "package_type_anchor"
    missing_type = _MISSING_TYPE_RE.match(message)
    if missing_type is not None and _created_in_a_schema(source, missing_type.group(1)):
        return "package_type_reference"
    if _COLLECTION_METHOD_RE.search(at):
        return "bulk_collect"
    if _CONDITIONAL_COMPILATION_RE.search(at):
        return "conditional_compilation"
    if _SUPPLIED_CALL_RE.match(at):
        return "supplied_package_call"
    unresolved = _UNRESOLVED_NAME_RE.match(message)
    if unresolved is not None and _in_a_default(text, unresolved.group(1)):
        return "package_constant_default"
    if _SPLICED_CONSTANT_RE.search(at):
        return "package_constant_chain"
    if _TRIGGER_FUNCTION_RE.search(text):
        return "trigger_package_call" if _BARE_CALL_RE.match(at) else None
    if _EMPTY_PARENS_CALL_RE.match(at):
        return "repeated_package_call"
    return None


def classify_errors(raw_errors: Sequence[_RawError], prepared: Sequence[_PreparedFile], dialect: str) -> list[LoadError]:
    by_script = {p.script_name: p for p in prepared}
    findings_cache: dict[str, list[Finding]] = {}
    taken: dict[str, set[int]] = {}
    out: list[LoadError] = []
    for raw in raw_errors:
        p = by_script[raw.script]
        if raw.script not in findings_cache:
            # The detectors read the generated file the way --verify does:
            # the VERBATIM ones find the Oracle construct ora2pg copied in.
            source = p.source.encode("utf-8", errors="surrogateescape").decode("utf-8", errors="replace")
            try:
                findings_cache[raw.script] = scan_source(source, dialect=dialect, errors=[])
            except Exception:
                findings_cache[raw.script] = []
        out.append(_classify(raw, p, findings_cache[raw.script], taken.setdefault(raw.script, set()), dialect))
    return out


# --- the whole check -------------------------------------------------------


def run_load_check(
    files: Sequence[Path],
    target: Target,
    *,
    dialect: str = "oracle",
    psql_bin: str = "psql",
    docker_bin: str = "docker",
) -> LoadCheckResult:
    """Load `files` (already in load order, see order_files()) into
    `target` and report what failed. Raises LoadCheckError when the check
    itself cannot run."""
    started = time.perf_counter()
    workdir = Path(tempfile.mkdtemp(prefix="ora2pg-gap-load-check-"))
    try:
        prepared, skipped, neutralised = _prepare(files, workdir)
        # What actually ran: the statements sanitize() blanked are not.
        statements = sum(len(p.parsed.statements) for p in prepared) - sum(
            1 for _, n in neutralised if n.kind != "meta"
        )
        if not prepared:
            return LoadCheckResult(
                target=target.describe(),
                server_version=None,
                files=(),
                statements=0,
                errors=(),
                neutralised=tuple(neutralised),
                skipped_files=tuple(skipped),
                elapsed_seconds=time.perf_counter() - started,
            )
        if target.kind == "docker":
            (workdir / "driver.sql").write_text(_driver_script(_REMOTE_DIR, prepared), encoding="utf-8")
            stdout, stderr = _run_docker(target.value, workdir, docker_bin)
        else:
            (workdir / "driver.sql").write_text(_driver_script(workdir.as_posix(), prepared), encoding="utf-8")
            stdout, stderr = _run_dsn(target.value, workdir, psql_bin)
        if f"{_MARK}:done" not in stdout:
            # psql stopped partway (the connection dropped, the server
            # went away). What it reported is real, but the rest was
            # never tried -- not a result to present as complete.
            raise LoadCheckError("load_check_incomplete", detail=stderr.strip()[-2000:])
        raw_errors = parse_psql_errors(stderr, [p.script_name for p in prepared])
        errors = classify_errors(raw_errors, prepared, dialect)
        return LoadCheckResult(
            target=target.describe(),
            server_version=server_version(stdout),
            files=tuple(str(p.path) for p in prepared),
            statements=statements,
            errors=tuple(errors),
            neutralised=tuple(neutralised),
            skipped_files=tuple(skipped),
            elapsed_seconds=time.perf_counter() - started,
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
