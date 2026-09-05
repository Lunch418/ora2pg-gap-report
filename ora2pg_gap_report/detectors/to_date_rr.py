import re

from .. import plsql_lex
from ..detector_spec import DetectorSpec, MASK_COMMENTS_ONLY, build

# TO_DATE/TO_TIMESTAMP whose format model contains RR or RRRR. The format
# model is a string literal, so this is one of the two detectors that run
# against mask_comments_only(): mask_strings_and_comments() would blank
# the very text being matched. The call keyword is still required in front
# of the literal, so a bare 'RR' inside an unrelated string (a message, a
# column comment) is not enough to trigger a finding. RRRR is included
# because it is the same Oracle-only family of format code -- PostgreSQL
# knows neither.
_TO_DATE_RR_RE = re.compile(
    r"\bTO_(?:DATE|TIMESTAMP(?:_TZ)?)\s*\([^;()]*?'[^']*\bRR(?:RR)?\b[^']*'",
    re.IGNORECASE,
)

_DOC = """Detect Oracle's RR/RRRR two-digit-year format code inside a
TO_DATE/TO_TIMESTAMP format model. ora2pg leaves it in place;
PostgreSQL does not recognise it and silently produces year 1 BC
instead of raising anything. See
docs/research/gap-058-to-date-rr.md.

Matched against mask_comments_only() rather than the usual fully
masked view, because the format model this is about *is* a string
literal -- while commented-out code still must not match."""

SPEC = DetectorSpec(
    name="to_date_rr",
    dialect="oracle",
    severity="high",
    pattern=_TO_DATE_RR_RE,
    snippet=lambda m: m.group(0).split("(")[0].strip().upper() + "(... 'RR' ...)",
    search_mask=MASK_COMMENTS_ONLY,
)

find_to_date_rr = build(SPEC, plsql_lex)
find_to_date_rr.__doc__ = _DOC
