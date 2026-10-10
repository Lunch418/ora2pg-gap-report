from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_comments_only,
    mask_strings_and_comments,
)

# Oracle's alternative-quoting mechanism: q'<delim> ... <delim>'  (also
# spelled nq'...' for national character literals). Only the opening
# three characters are matched -- the closing delimiter depends on the
# opening one ([ pairs with ], { with }, ( with ), < with >, anything
# else with itself) and plsql_lex already implements that pairing for
# masking purposes; repeating it here would duplicate the rule with no
# gain, since the finding is about the literal *starting* at all.
_CLOSING = {"[": "]", "{": "}", "(": ")", "<": ">"}


def _ident_char(ch: str) -> bool:
    return ch.isalnum() or ch in "_$#"


def _alt_quote_starts(text: str) -> list[tuple[int, str]]:
    """(position, delimiter) of each q'...' / nq'...' literal in `text`
    (comments already blanked), outside other string literals: a q right
    before an ordinary literal's closing quote -- 'a CD-ROM q' -- is the
    end of a word, not alternative quoting."""
    starts = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if (
            ch in "qQ"
            and text[i + 1 : i + 2] == "'"
            and i + 2 < n
            and (
                i == 0
                or not _ident_char(text[i - 1])
                or (text[i - 1] in "nN" and (i < 2 or not _ident_char(text[i - 2])))
            )
        ):
            start = i - 1 if i > 0 and text[i - 1] in "nN" else i
            delim = text[i + 2]
            end = text.find(_CLOSING.get(delim, delim) + "'", i + 3)
            starts.append((start, delim))
            i = end + 2 if end >= 0 else n
        elif ch == "'":
            i += 1
            while i < n:
                if text[i] == "'":
                    if text[i + 1 : i + 2] == "'":
                        i += 2
                        continue
                    break
                i += 1
            i += 1
        else:
            i += 1
    return starts


def find_alt_quote_literals(source: str) -> list[Finding]:
    """Detect Oracle's q'...' / nq'...' alternative-quoting literals.
    ora2pg copies them through unchanged and PostgreSQL has no such
    syntax, so the generated code fails to parse. See
    docs/research/gap-062-alt-quote-literal.md.

    Matched against mask_comments_only() rather than the usual fully
    masked view: mask_strings_and_comments() understands q-quotes and
    blanks them out, which is exactly the text this detector exists to
    find, while the raw source would also match commented-out code."""
    clean = mask_strings_and_comments(source)
    literals = mask_comments_only(source)
    name_index = enclosing_object_name_index(clean)
    findings: list[Finding] = []

    for start, delim in _alt_quote_starts(literals):
        findings.append(
            Finding(
                detector="alt_quote_literal",
                severity="high",
                object_name=enclosing_object_name(name_index, start),
                line=line_at(source, start),
                snippet=f"q'{delim}...",
                message_id="alt_quote_literal",
            )
        )

    return findings
