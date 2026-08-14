#!/usr/bin/env python3
"""Bundle ora2pg-gap-report and its dependencies into a single archive
that installs on a machine with **no internet access** — exactly the
closed-network / air-gapped environments this project targets.

Run this on a machine WITH internet access, from a checkout of this repo:

    python scripts/build_offline_bundle.py                 # base install only
    python scripts/build_offline_bundle.py --oracle         # + python-oracledb
    python scripts/build_offline_bundle.py --oracle --dev   # + pytest too

This writes ora2pg-gap-report-offline.tar.gz to --out (default: repo root).
Move it to the target machine however your contour allows (scp, sftp,
USB, a jump host you paste it through by hand) and there run, passing
back whichever extras you built with (comma- or space-separated, same
thing — matters only if you used --oracle/--dev above):

    tar xzf ora2pg-gap-report-offline.tar.gz
    cd ora2pg-gap-report-offline
    ./install.sh oracle dev            # or: python3 install.py oracle dev
    ./install.sh                       # no extras — base install only

Both installers call `pip install --no-index --find-links=./wheels ...`
— pip resolves entirely from the bundled wheels, no PyPI contact at all.

Cross-platform note: rich and its dependencies (markdown-it-py, pygments,
mdurl) are pure Python — one set of wheels works everywhere. oracledb
(only pulled in by --oracle) ships platform-specific wheels. If the
target machine's OS/CPU/Python version differs from the machine you run
this script on, pass e.g. --platform manylinux2014_x86_64
--python-version 311 --abi cp311 to fetch the *target's* wheels instead
of building for the machine you're standing on — see `pip download --help`
for the exact values your target needs.
"""

import argparse
import glob
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_INSTALL_SH = """\
#!/bin/sh
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
EXTRAS=""
for arg in "$@"; do
    if [ -z "$EXTRAS" ]; then EXTRAS="$arg"; else EXTRAS="$EXTRAS,$arg"; fi
done
if [ -n "$EXTRAS" ]; then
    PKG="ora2pg-gap-report[$EXTRAS]"
else
    PKG="ora2pg-gap-report"
fi
PY="$(command -v python3 || command -v python)"
"$PY" -m pip install --no-index --find-links="$DIR/wheels" "$PKG"
"""

_INSTALL_PY = '''\
#!/usr/bin/env python3
"""Offline install helper — run on the target (no-internet) machine.
Usage: python3 install.py [extra ...]   e.g. python3 install.py oracle dev
"""
import subprocess
import sys
from pathlib import Path

wheels_dir = Path(__file__).resolve().parent / "wheels"
extras = ",".join(sys.argv[1:])
package = f"ora2pg-gap-report[{extras}]" if extras else "ora2pg-gap-report"
subprocess.check_call(
    [sys.executable, "-m", "pip", "install", "--no-index",
     "--find-links", str(wheels_dir), package]
)
'''


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--oracle", action="store_true", help="include python-oracledb (live Oracle export)")
    parser.add_argument("--dev", action="store_true", help="include pytest (to run the test suite offline too)")
    parser.add_argument("--out", type=Path, default=REPO_ROOT, help="directory to write the .tar.gz into")
    parser.add_argument(
        "--platform",
        default=None,
        help="target platform tag, e.g. manylinux2014_x86_64 (passed to `pip download`, "
        "for building the bundle on a different machine than the install target)",
    )
    parser.add_argument("--python-version", default=None, help="target Python version, e.g. 311 (see --platform)")
    parser.add_argument("--abi", default=None, help="target ABI tag, e.g. cp311 (see --platform)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    extras = []
    if args.oracle:
        extras.append("oracle")
    if args.dev:
        extras.append("dev")

    staging = args.out / "ora2pg-gap-report-offline"
    wheels_dir = staging / "wheels"
    if staging.exists():
        shutil.rmtree(staging)
    wheels_dir.mkdir(parents=True)

    # Step 1: build our own wheel. Always via `pip wheel` on the *current*
    # machine, regardless of --platform/etc — the package itself is pure
    # Python (py3-none-any), so there is nothing target-platform-specific
    # to cross-build here; only its dependencies (oracledb, specifically)
    # can differ by platform.
    print("+ building the project's own wheel", file=sys.stderr)
    subprocess.check_call(
        [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "-w", str(wheels_dir)],
        cwd=REPO_ROOT,
    )
    own_wheels = glob.glob(str(wheels_dir / "ora2pg_gap_report-*.whl"))
    if not own_wheels:
        print("error: pip wheel didn't produce ora2pg_gap_report-*.whl", file=sys.stderr)
        return 1
    own_wheel = own_wheels[0]

    # Step 2: resolve and download every dependency (base + requested
    # extras). Deliberately `pip download` pointed at the *wheel file*
    # from step 1, not `pip wheel .` on the source directory: only
    # `pip download` accepts --platform/--python-version/--abi for
    # cross-platform bundling, and (verified directly) `pip download`
    # given a local *directory* requirement reports success but does not
    # reliably place the built artifact in -d in this pip version — giving
    # it an already-built wheel file sidesteps that entirely.
    requirement = f"{own_wheel}[{','.join(extras)}]" if extras else own_wheel
    cmd = [sys.executable, "-m", "pip", "download", requirement, "-d", str(wheels_dir)]
    if args.platform or args.python_version or args.abi:
        cmd += ["--only-binary=:all:"]
        if args.platform:
            cmd += ["--platform", args.platform]
        if args.python_version:
            cmd += ["--python-version", args.python_version]
        if args.abi:
            cmd += ["--abi", args.abi]
    print("+ " + " ".join(cmd), file=sys.stderr)
    subprocess.check_call(cmd, cwd=REPO_ROOT)

    (staging / "install.sh").write_text(_INSTALL_SH)
    (staging / "install.sh").chmod(0o755)
    (staging / "install.py").write_text(_INSTALL_PY)
    (staging / "install.py").chmod(0o755)
    extras_hint = " " + " ".join(extras) if extras else ""
    (staging / "README.txt").write_text(
        "Офлайн-установка ora2pg-gap-report\n"
        "===================================\n\n"
        "На машине БЕЗ интернета, после переноса и распаковки этого архива:\n\n"
        f"    ./install.sh{extras_hint}\n"
        f"    (или: python3 install.py{extras_hint})\n\n"
        "Ничего не обращается в сеть — pip ставит только из wheels/ рядом с "
        "этим файлом (--no-index --find-links).\n"
    )

    archive_path = args.out / "ora2pg-gap-report-offline.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(staging, arcname="ora2pg-gap-report-offline")
    shutil.rmtree(staging)

    print(f"\nГотово: {archive_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
