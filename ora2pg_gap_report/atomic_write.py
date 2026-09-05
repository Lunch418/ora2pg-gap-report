"""One helper: write a text file so a reader never sees a half-written one.

Every file this tool writes -- a baseline snapshot, a report, and most
importantly a user's own SQL file under `--fix --write` -- used to go
straight to the destination path with `Path.write_text()`. That is not
atomic: a crash, a full disk or a `kill` partway through leaves a
truncated file where a valid one used to be. For a baseline that means
the next `--baseline` run fails to parse it; for `--fix --write` it means
the user's source file is now corrupt, and the tool that corrupted it was
the one advertised as making a safe mechanical fix.

Writing to a temporary file first and renaming it into place makes the
switch atomic on POSIX and on Windows (os.replace is atomic on both): a
reader sees either the old contents or the new ones, never a partial
write. The temp file goes in the *destination's own directory* rather
than the system temp dir, because a rename is only atomic within one
filesystem -- across a mount boundary os.replace falls back to a
copy-then-delete that is exactly the non-atomic behaviour this exists to
avoid (and on some platforms fails outright with EXDEV).
"""

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO


@contextmanager
def open_text_atomic(path: Path, encoding: str = "utf-8") -> Iterator[IO[str]]:
    """A writable text handle whose contents land at `path` atomically,
    or not at all.

    The streaming half of write_text_atomic(), for callers producing
    output too large to hold as one string: a report over a big scan is
    tens of megabytes, and building it in memory to hand to write_text_
    atomic() costs several times that in intermediate objects. Everything
    that makes the non-streaming version safe holds here too -- temp file
    in the destination's own directory, fsync before the rename, cleanup
    on any failure -- and the file appears at `path` only on a clean exit
    from the block.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # delete=False because the file has to outlive the handle: it gets
    # renamed into place below, not deleted. Same directory as the
    # destination -- see the module docstring for why that matters.
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        encoding=encoding,
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    try:
        with tmp:
            yield tmp
            # The rename below is atomic with respect to *readers*, but
            # on a crash the OS may not have flushed the data yet, which
            # would leave the renamed file empty. Forcing it out first
            # keeps the guarantee across a power loss, not just a crash.
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp.name, path)
    except BaseException:
        # Any failure -- OSError, or a KeyboardInterrupt mid-write --
        # leaves a stray temp file next to the user's real one otherwise.
        # Best-effort: if even the cleanup fails there is nothing useful
        # left to do but let the original exception surface.
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise


def write_text_atomic(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write `text` to `path` atomically, creating parent directories.

    `--save reports/baseline.json` into a directory that doesn't exist
    yet used to fail with a bare [Errno 2]; the parent is created here
    instead, since every caller wants the file written and none of them
    has a reason to insist the directory already exist.

    OSError propagates exactly as it did from Path.write_text(), so every
    existing caller's error handling keeps working unchanged -- what
    changes is only that a failure now leaves the previous file intact
    instead of a truncated one.
    """
    with open_text_atomic(path, encoding) as handle:
        handle.write(text)
