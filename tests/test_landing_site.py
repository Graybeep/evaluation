"""Structural guards for the landing site (`landing/`).

These are cheap, portable checks — no browser, no node — for the failure shapes
that are invisible in a screenshot and silent at runtime:

  * a page that lost a `<script src>` renders an empty shell, which reads as
    "nothing found" rather than "never loaded" (§7.10, again);
  * a `data-tip-key` with no glossary entry renders a "?" that explains
    nothing, or nothing at all where an explanation was intended;
  * a missing `<meta charset>` silently mojibakes every em dash on the page,
    which is how the single-page version shipped for a while.

The rendering itself is covered separately by a DOM-shim harness; what cannot
be asserted without a browser is stated here rather than assumed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

LANDING = Path(__file__).resolve().parent.parent / "landing"
PAGES = ("index.html", "connect.html", "results.html")
ASSETS = ("are.css", "common.js", "tips.js", "report.js")

pytestmark = pytest.mark.skipif(not LANDING.exists(), reason="landing/ not present")


def read(rel: str) -> str:
    return (LANDING / rel).read_text(encoding="utf-8")


@pytest.mark.parametrize("page", PAGES)
def test_every_page_exists_and_declares_its_encoding(page):
    """No doctype/charset means windows-1252, which mangles every em dash."""
    html = read(page)
    head = html[:1024]
    assert html.lstrip().lower().startswith("<!doctype html>"), page
    assert '<meta charset="utf-8">' in head, f"{page}: charset must be in the first 1KB"
    assert 'name="viewport"' in head, page
    assert "<title>" in head, page


@pytest.mark.parametrize("page", PAGES)
def test_every_page_loads_the_shared_runtime(page):
    """A page that silently drops a script renders an empty shell that looks
    like a clean result. Assert the positive condition (§7.10)."""
    html = read(page)
    for need in ("assets/are.css", "assets/data.js", "assets/common.js", "assets/tips.js"):
        assert need in html, f"{page} does not load {need}"


def test_results_page_loads_the_report_renderer():
    assert "assets/report.js" in read("results.html")


@pytest.mark.parametrize("asset", ASSETS)
def test_shared_assets_exist_and_are_not_empty(asset):
    p = LANDING / "assets" / asset
    assert p.exists(), f"missing asset: {asset}"
    assert p.stat().st_size > 400, f"{asset} is suspiciously small"


def test_baked_data_defines_the_global_the_pages_read():
    js = read("assets/data.js")
    assert js.lstrip().startswith("/*"), "data.js should carry its generated-by header"
    assert "window.ARE_DATA = " in js
    blob = js.split("window.ARE_DATA = ", 1)[1].rsplit(";", 1)[0]
    data = json.loads(blob)
    assert data.get("baked") is True
    assert data.get("model_version"), "provenance stamp must name the model (§4.5)"
    assert data.get("mode") in ("OFFLINE", "ONLINE")


# --------------------------------------------------------------- explainers
def glossary_keys() -> set[str]:
    tips = read("assets/tips.js")
    body = re.search(r"var TIPS = \{(.*?)\n  \};", tips, re.S)
    assert body, "could not find the TIPS glossary in tips.js"
    return set(re.findall(r"^\s{4}([A-Za-z0-9_]+):", body.group(1), re.M))


DYNAMIC_PREFIXES = ("cat_",)   # built at runtime as q('cat_' + k, ...)


def consumer_sources() -> str:
    """Everything that can reference a tip key — pages plus the two renderers.
    tips.js is excluded: it *defines* the keys, so including it would make
    every entry trivially "used"."""
    return "\n".join([read(p) for p in PAGES]
                     + [read("assets/common.js"), read("assets/report.js")])


def used_keys() -> set[str]:
    """Keys referenced anywhere, by any route.

    Deliberately a literal scan rather than a `q('...')` regex: keys also reach
    the renderer through a data table (`blockUnmeasured`) and through markup
    attributes, and a regex tuned to one call shape silently under-reports the
    others — which would turn this test into a check that passes because it
    cannot see, the exact failure mode §7.10 is about."""
    src = consumer_sources()
    return {k for k in glossary_keys()
            if re.search(r"""['"]%s['"]""" % re.escape(k), src)}


def referenced_keys() -> set[str]:
    """Keys the markup and renderers actually ask for — found independently of
    the glossary, so a typo shows up as a key with no entry."""
    refs: set[str] = set()
    for page in PAGES:
        refs |= set(re.findall(r'data-tip-key="([^"]+)"', read(page)))
    src = consumer_sources()
    refs |= set(re.findall(r"q\('([A-Za-z0-9_]+)'", src))
    # `q('cat_' + k, …)` yields the bare prefix; it is covered by its own test.
    return {r for r in refs if r not in DYNAMIC_PREFIXES}


def test_every_explainer_chip_resolves_to_a_glossary_entry():
    """A key with no entry renders nothing — a "?" the reader can't use, or a
    silently missing explanation. Both are worse than a loud failure here."""
    missing = sorted(referenced_keys() - glossary_keys())
    assert missing == [], f"tip keys with no glossary entry: {missing}"


def test_category_chips_have_entries_since_they_are_built_dynamically():
    """`q('cat_' + k, k)` is assembled at runtime, so the static sweep above
    cannot see it. Named explicitly rather than left uncovered."""
    keys = glossary_keys()
    for cat in ("safety", "correctness", "robustness", "efficiency"):
        assert f"cat_{cat}" in keys, f"missing glossary entry cat_{cat}"


def test_no_glossary_entry_is_dead_weight():
    unused = sorted(glossary_keys() - used_keys()
                    - {f"cat_{c}" for c in
                       ("safety", "correctness", "robustness", "efficiency")})
    assert unused == [], f"glossary entries nothing references: {unused}"


# ----------------------------------------------------------------- content
@pytest.mark.parametrize("page", PAGES)
def test_pages_carry_no_commercial_framing(page):
    """ARE is a research demo. Pricing tiers were removed once, and the
    "free / no billing" framing that replaced them was removed again — it
    answered a question nobody asked and implied a paid tier existed."""
    text = read(page).lower()
    for banned in ("no billing", "free to use", "no seats", "no tiers",
                   "licence key", "usage cap", "pricing"):
        assert banned not in text, f"{page} contains commercial framing: {banned!r}"


@pytest.mark.parametrize("page", PAGES)
def test_internal_links_point_at_files_that_exist(page):
    """A multi-page site's cheapest way to break is a link to a renamed page."""
    for href in re.findall(r'href="([^"#:]+\.html)[^"]*"', read(page)):
        assert (LANDING / href).exists(), f"{page} links to missing {href}"


def test_the_page_that_shows_a_score_also_shows_what_was_not_measured():
    """The §7.10 rule, asserted on the surface a reader actually sees: the
    report renderer must have a block for absent measurements, and must be
    able to withhold a grade entirely rather than print a number from data the
    platform rejected."""
    js = read("assets/report.js")
    assert "blockUnmeasured" in js
    assert "NOT REPORTABLE" in js
    assert "not measured" in js.lower()
    assert "UNEVALUATED" in read("connect.html"), (
        "the MCP page must say which checks cannot run, not quietly omit them")


# ------------------------------------------------------------ script syntax
def _node() -> str | None:
    from shutil import which
    return which("node")


@pytest.mark.parametrize("page", PAGES)
def test_inline_page_scripts_parse(page, tmp_path):
    """The pages carry an inline bootstrap each. A syntax error there is
    invisible in the markup and silently leaves the page unrendered — which,
    on this site, looks like an agent with no findings.

    Skipped (loudly, never silently passed) when node is unavailable.
    """
    node = _node()
    if not node:
        pytest.skip("node not on PATH — inline script syntax UNVERIFIED, not verified")

    import subprocess

    blocks = re.findall(r"<script>\n(.*?)</script>", read(page), re.S)
    assert blocks, f"{page} has no inline bootstrap script"
    for i, src in enumerate(blocks):
        f = tmp_path / f"{page}.{i}.js"
        f.write_text(src, encoding="utf-8")
        r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, f"{page} inline script #{i} does not parse:\n{r.stderr}"


@pytest.mark.parametrize("asset", [a for a in ASSETS if a.endswith(".js")])
def test_shared_scripts_parse(asset, tmp_path):
    node = _node()
    if not node:
        pytest.skip("node not on PATH — asset syntax UNVERIFIED, not verified")

    import subprocess

    r = subprocess.run([node, "--check", str(LANDING / "assets" / asset)],
                       capture_output=True, text=True)
    assert r.returncode == 0, f"{asset} does not parse:\n{r.stderr}"
