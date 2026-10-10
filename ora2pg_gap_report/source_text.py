"""Reading a source file whatever Unicode encoding it is in.

SSMS saves scripts as UTF-16 by default, with a byte-order mark. Read as
UTF-8, such a file is every other byte NUL: nothing in it matches, and a
scan of it comes back clean -- found in Microsoft's own sample scripts
(Wide World Importers). The mark says which encoding it is; a UTF-16 file
without one shows itself by those NUL bytes.

Everything else is UTF-8, decoded the way each caller needs: `replace`
to scan, `surrogateescape` to rewrite a file and keep the bytes that are
not UTF-8 (a cp1251 comment) exactly as they were.
"""

from __future__ import annotations

from pathlib import Path

# Longest first: UTF-32 LE starts with UTF-16 LE's mark.
_MARKS = (
    (b"\xff\xfe\x00\x00", "utf-32-le-bom"),
    (b"\x00\x00\xfe\xff", "utf-32-be-bom"),
    (b"\xff\xfe", "utf-16-le-bom"),
    (b"\xfe\xff", "utf-16-be-bom"),
)
_BOM = "\ufeff"


def detect_encoding(data: bytes) -> str:
    """'utf-16-le-bom' and the like (a mark, its byte order), 'utf-16-le'
    or 'utf-16-be' (no mark), or 'utf-8'."""
    for mark, encoding in _MARKS:
        if data.startswith(mark):
            return encoding
    head = data[:200]
    if len(head) >= 4 and head.count(0) * 3 >= len(head):
        # ASCII text in UTF-16: a NUL beside every character.
        if head[1] == 0 and head[0] != 0:
            return "utf-16-le"
        if head[0] == 0 and head[1] != 0:
            return "utf-16-be"
    return "utf-8"


def codec(encoding: str) -> tuple[str, str]:
    """(Python codec, text to put in front -- the mark) for an encoding
    detect_encoding() named."""
    if encoding.endswith("-bom"):
        return encoding[: -len("-bom")], _BOM
    return encoding, ""


def decode_source(data: bytes, errors: str = "replace") -> tuple[str, str]:
    """(text, encoding) of `data`. A UTF-16/32 mark is dropped from the
    text; a UTF-8 one stays, as U+FEFF, so a rewrite keeps it."""
    encoding = detect_encoding(data)
    if encoding == "utf-8":
        return data.decode("utf-8", errors=errors), encoding
    name, mark = codec(encoding)
    text = data.decode(name, errors="replace")
    return (text[len(mark) :] if mark and text.startswith(mark) else text), encoding


def read_source(path: Path, errors: str = "replace") -> str:
    """The text of the source file at `path`, in whatever encoding."""
    return decode_source(path.read_bytes(), errors)[0]


def encode_source(text: str, encoding: str) -> bytes:
    """`text` encoded back the way decode_source() found it: the same
    byte order and mark, or UTF-8 keeping any byte surrogateescape
    carried."""
    if encoding == "utf-8":
        return text.encode("utf-8", errors="surrogateescape")
    name, mark = codec(encoding)
    return (mark + text).encode(name)
