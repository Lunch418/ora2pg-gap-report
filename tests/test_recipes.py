import re
import shutil
import subprocess
import sys

import pytest

from ora2pg_gap_report import messages
from ora2pg_gap_report.core import DIALECTS, _DETECTORS_BY_DIALECT
from ora2pg_gap_report.gap_registry import gap_by_detector
from ora2pg_gap_report.recipes import RECIPES, RECIPES_DIR, recipe_for, recipe_path, recipe_url

SQL_BLOCK = re.compile(r"^```sql\n(.*?)^```", re.S | re.M)
LANGS = ("en", "ru")
# Arrow, em and en dash, curly and angle quotes -- spelled as code points so
# this file itself stays ASCII.
_NON_ASCII_PUNCTUATION = "".join(map(chr, (0x2192, 0x2014, 0x2013, 0x201C, 0x201D, 0x00AB, 0x00BB)))


def _page(recipe, lang):
    path = recipe_path(recipe, lang)
    assert path is not None, f"{recipe.slug}: no {lang} page"
    return path.read_text(encoding="utf-8")


def _all_detectors():
    scanned = {d.__module__.rsplit(".", 1)[-1] for dialect in DIALECTS for d in _DETECTORS_BY_DIALECT[dialect]}
    # connect_by runs only under --check-connect-by, outside the scan tuples
    return scanned | {"connect_by"}


def test_every_recipe_has_both_pages_with_runnable_sql():
    for recipe in RECIPES:
        counts = {lang: len(SQL_BLOCK.findall(_page(recipe, lang))) for lang in LANGS}
        assert counts["en"] > 0, recipe.slug
        # the Russian page is a translation: same code, block for block
        assert counts["en"] == counts["ru"], (recipe.slug, counts)


def test_recipe_detectors_exist_and_each_belongs_to_one_recipe():
    known = _all_detectors()
    seen = set()
    for recipe in RECIPES:
        for detector in recipe.detectors:
            assert detector in known, (recipe.slug, detector)
            assert detector not in seen, detector
            seen.add(detector)
            assert recipe_for(detector) is recipe


def test_each_page_names_exactly_the_gaps_of_its_detectors():
    for recipe in RECIPES:
        expected = {gap_by_detector(d).number for d in recipe.detectors if gap_by_detector(d) is not None}
        for lang in LANGS:
            first_lines = "\n".join(_page(recipe, lang).splitlines()[:12])
            assert set(re.findall(r"GAP-(\d{3})", first_lines)) == expected, (recipe.slug, lang)


def test_the_index_lists_every_recipe_in_both_languages():
    for lang, name in (("en", "README.md"), ("ru", "README.ru.md")):
        index = (RECIPES_DIR / name).read_text(encoding="utf-8")
        linked = set(re.findall(r"\]\(([a-z-]+)(?:\.ru)?\.md\)", index))
        assert linked == {r.slug for r in RECIPES}, lang


def test_pages_use_plain_ascii_punctuation():
    # The project writes -> and - rather than arrows, dashes and curly quotes.
    for path in RECIPES_DIR.glob("*.md"):
        bad = [c for c in path.read_text(encoding="utf-8") if c in _NON_ASCII_PUNCTUATION]
        assert not bad, (path.name, bad)


def test_recipe_url_points_at_the_language():
    recipe = recipe_for("connect_by")
    assert recipe_url(recipe, "en").endswith("/docs/recipes/hierarchical-queries.md")
    assert recipe_url(recipe, "ru").endswith("/docs/recipes/hierarchical-queries.ru.md")
    assert recipe_for("no_such_detector") is None


def test_recipe_titles_are_set_in_both_languages():
    for recipe in RECIPES:
        assert recipe.title("en") and recipe.title("ru")
        assert recipe.title("en") != recipe.title("ru") or recipe.slug == "pivot-unpivot", recipe.slug
    # every detector a recipe covers has a title of its own to show beside it
    for recipe in RECIPES:
        for detector in recipe.detectors:
            assert messages.title(detector, "en") != detector, detector


def _docker_usable():
    if not sys.platform.startswith("linux") or shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@pytest.mark.docker
@pytest.mark.skipif(not _docker_usable(), reason="needs a working docker (Linux)")
@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("recipe", RECIPES, ids=lambda r: r.slug)
def test_recipe_code_runs_on_real_postgresql(recipe, lang, tmp_path):
    """Every ```sql block of the page, in order, through --load-check: not
    one statement may fail, and the page's own DO ... ASSERT blocks are
    what check the pattern does what the page says."""
    from ora2pg_gap_report.load_check import parse_target, run_load_check

    script = tmp_path / f"{recipe.slug}.{lang}.sql"
    script.write_text("\n".join(SQL_BLOCK.findall(_page(recipe, lang))), encoding="utf-8")
    result = run_load_check([script], parse_target("docker"))
    assert result.errors == (), [(e.line, e.sqlstate, e.message) for e in result.errors]
    assert result.neutralised == ()
