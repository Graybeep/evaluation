# -*- coding: utf-8 -*-
"""Shared chrome for the three pages.

Not a template engine — the pages are plain HTML and stay readable. This just
holds the two blocks that must be byte-identical across them (nav, footer) so
they cannot drift apart, and is imported by nothing at runtime: it is used once,
by hand, to generate the pages. Kept in-tree so regenerating is possible.
"""

MARK = """<svg class="brand-mk" viewBox="0 0 32 32" fill="none" aria-hidden="true">
        <rect x="1.2" y="1.2" width="29.6" height="29.6" rx="8.4"
              stroke="currentColor" stroke-width="1.6" opacity=".45"/>
        <path d="M9 20.5 13.4 12l4.2 8.2 2.4-4.2H23" stroke="currentColor"
              stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="13.4" cy="12" r="2.1" fill="currentColor"/>
      </svg>"""


def head(title, desc):
    return f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/are.css">
"""


def nav(cta_href, cta_text):
    return f"""<a class="skip" href="#main">Skip to content</a>
<header class="nav">
  <div class="wrap nav-in">
    <a class="brand" href="index.html">
      {MARK}
      <span>Agent Reliability Engine</span>
    </a>
    <nav class="nav-links" aria-label="Primary">
      <a href="index.html" data-nav="index.html">Home</a>
      <a href="connect.html" data-nav="connect.html">Connect your agent</a>
      <a href="results.html" data-nav="results.html">Report card</a>
    </nav>
    <a class="btn btn-ghost nav-cta" href="{cta_href}">{cta_text}</a>
  </div>
</header>
"""


FOOTER = """<footer>
  <div class="wrap">
    <div class="ft-grid">
      <a class="brand" href="index.html">
        """ + MARK + """
        <span>Agent Reliability Engine</span>
      </a>
      <nav class="ft-links" aria-label="Footer">
        <a href="index.html">Home</a><a href="connect.html">Connect your agent</a>
        <a href="results.html">Report card</a>
      </nav>
    </div>
    <p class="ft-note">
      <strong>Stated plainly:</strong> the LLM judge is uncalibrated — no human-labelled
      agreement study has been run, and judge-derived findings are advisory. Scenarios come
      from 13 hand-authored templates, so coverage is bounded by template imagination rather
      than by the real failure distribution. One domain; cross-domain transfer is
      unvalidated. Absolute scores are not comparable across agents built on different
      toolsets — only paired, same-suite comparisons are meaningful.
    </p>
    <p class="prov" id="prov">Data: not baked. Run <code>python landing/build.py</code>.</p>
  </div>
</footer>

<div id="tip" role="tooltip" aria-hidden="true"></div>
<script src="assets/data.js"></script>
<script src="assets/common.js"></script>
<script src="assets/tips.js"></script>
"""
