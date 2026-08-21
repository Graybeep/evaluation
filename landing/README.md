# landing/

Landing page for ARE. Static, self-contained, no build toolchain — but **connected to the
engine**: every number it shows is read from this repository's run artifacts.

```bash
python landing/build.py                            # bake real engine output into the page
python -m http.server 8080 --directory landing     # then open http://localhost:8080
```

`index.html` also opens fine by double-click (`file://`) — the data is baked *into* the
page, not fetched, precisely so that works.

## The pipeline connection

```
runs/calib-*/scorecard.json     ← are.score.compute
runs/calibration.json           ← cli.py calibrate  (acceptance verdict + 6 checks)
runs/demo-pushover-v2/comparison.json ← are.score.regression  (McNemar + BH)
runs/history.jsonl              ← append-only run history
        │
        └──> landing/build.py ──> landing/data/site.json
                              └─> <script id="are-data"> inside index.html
                                        │
                                        └──> the page renders it
```

`build.py` **reads the engine's own output and never re-derives a number**, so the page
cannot drift and disagree with the CLI about a verdict. Re-run it after any new run; it is
idempotent and rewrites the same `<script>` block.

What is live on the page today:

| Panel | Source | Current value |
|---|---|---|
| Agent picker + composite/CI | `runs/calib-<agent>/scorecard.json` | clean 100.0, confabulator 92.2, looper 65.0, pushover 31.7 |
| Invalid rate + reportability | same | 0.0%, under the 5% ceiling |
| Flake quarantine tile | `flaky_measurable` | **NOT MEASURED** — the offline agents are deterministic |
| Top failure modes | `per_mode` | e.g. pushover `DESTRUCTIVE_ACTION` 38/60 |
| Acceptance banner | `runs/calibration.json` | `PASS` — 6/6 checks |
| Regression tiles | `comparison.json` | 31.67 → 41.67, +10.0, p=0.03125 |
| History chart | `runs/history.jsonl` | 24 runs, **4 unreportable** drawn as rings, not zeros |

### §7.10 is implemented here, not just cited

The page distinguishes four states that a careless dashboard would collapse into one:

| State | Renders as |
|---|---|
| measured, clean | the number, with its interval |
| **not baked** | "NOT BAKED — an absent measurement, not a passing one" |
| **missing artifact** | `MISSING` on that panel, listed in the footer provenance line |
| **unreportable run** (NaN composite) | a ring on the chart floor + `UNREPORTABLE` in the data table |
| **structurally unmeasurable** (flake vs. deterministic agent) | `n/a — NOT MEASURED`, never `0` |

Both paths are tested: the baked render and the never-baked render are each executed
against a DOM shim, and the assertions check for the *words*, not the absence of an error.

## No pricing, and no commercial framing at all — nothing on the page is invented

The pricing section is **gone** (removed 2026-08-21). ARE is not a product — `CLAUDE.md` §0
scopes it to "a working demo + a defensible measurement story" — so three invented tiers and
a `$0 / $249 / Custom` ladder described nothing that exists.

The **"free / no billing" framing that replaced it is also gone** (removed 2026-08-21). It
was the same mistake one level down: "Free to use. No tiers, no seats, no billing" answers a
commercial question nobody asked of a research demo, and implies there is a paid thing to
contrast with. `#use` now simply says the numbers are reproducible and lists the two
commands that reproduce them (`cli.py calibrate --offline --no-sandbox`, `cli.py
mcp-serve`). Each command is checked against `are/cli.py`'s real argument names.

The Streamlit console (`app.py`) was **deleted 2026-08-21** and its card removed from `#use`
along with it. The page is a static view of baked artifacts and cannot run the engine, so it
never substituted for the console — but a page advertising a command that no longer exists
is exactly the kind of untrue claim this repo spends its §7.10 discipline avoiding, so the
reference went when the file did.

The only cost-shaped statement left is factual and load-bearing: the offline path needs no
API key, which is why the whole demo runs with no spend.

Every claim on the page is now either a number read from a run artifact or a command in this
repository — no fabricated customer logos, no invented certifications, no "trusted by" line,
and no licence badge (the repo has no `LICENSE` file at time of writing). The footer carries
the §11 limitations.

## Explainer chips ("?")

Every figure, badge, statistic and piece of jargon on the page carries a small `?` that
explains it in plain words — 54 of them at time of writing. The rule applied: assume the
reader has never seen this project, an eval harness, or the statistics. "p-value" says what
a p-value *is*, and then says it tells you whether something changed and never how much.

- **One glossary, one bubble.** `window.ARETips.TIPS` holds every explanation; a single
  tooltip node is moved around the page rather than one bubble per chip.
- **Chips are declared, not hand-built.** Any element — static markup or JS-rendered —
  gets a chip by carrying `data-tip-key="<key>"`. `hydrate()` swaps those slots for real
  `<button>`s and is idempotent, so it is safe to call after every dynamic render.
  `paint()` re-hydrates the scorecard panel on each agent switch.
- **A key with no glossary entry renders nothing** rather than an empty chip, so a typo
  fails visibly instead of leaving a `?` that explains nothing.
- **Accessible.** Real buttons with `aria-label`, opened on hover *and* keyboard focus,
  `aria-describedby` while open, Escape to close, tap-to-toggle on touch, and
  `prefers-reduced-motion` honoured. The bubble flips above/below and clamps horizontally
  so it never lands off-screen.

Verified in-browser: all 54 chips hydrate, all resolve to a real glossary entry, none is
positioned off-screen, focus opens and Escape closes, and the count survives an agent
switch with no orphaned slots.

## Document head — charset is load-bearing

`index.html` had **no doctype, no `<html>`, and no `<meta charset>`** — it was a bare
fragment relying on browser error-recovery. Layout survived that; text did not. Served over
HTTP with no charset, the browser fell back to windows-1252 and every em dash, curly quote
and `·` rendered as mojibake (`â€"`, `Â·`). The explainer copy is full of those characters,
which is how it finally became obvious. Added `<!doctype html>`, `<html lang="en">`,
`<meta charset="utf-8">` and a viewport meta — the charset lands in the first 1024 bytes,
which is where the parser stops looking.

## Design

Generated with the `ui-ux-pro-max` skill, then recoloured to cream on request.

- **Pattern** — `trust-authority-conversion` (Hero ▸ Proof ▸ Solution ▸ CTA). The
  `--design-system` run first returned `FAQ/Documentation Landing`, a misroute; re-queried
  on `--domain landing`.
- **Style** — `glassmorphism`: `backdrop-filter: blur(15px)`, translucent white 58%, 1px
  light border, over a warm radial ground so the glass has something to refract.
- **Palette (cream)** — `#F6F1E7` paper, `#241F1A` ink, `#15754B` deep green accent,
  `#8A5A12` amber, `#B3261E` red. Every pairing is ≥4.5:1 against its surface; the
  ratios are noted inline in the token block.
- **Type** — JetBrains Mono / IBM Plex Sans.
- **Motion** — Subtle tier: 350ms scroll reveal, ease-out, IntersectionObserver rather than
  GSAP so the page stays dependency-free.
- **Chart** — chart-domain guidance for anomaly-on-timeseries: line with highlight markers,
  anomalies given a **distinct shape plus a table row** (never colour alone), plus an
  accessible data table.

Pre-delivery checklist: SVG icons (no emoji), `cursor: pointer` on controls, 220ms hover
transitions, visible focus rings, `prefers-reduced-motion` honoured, 44px touch targets,
screen-reader table behind the chart, `aria-pressed` on the agent picker.

## Verification

```bash
python landing/build.py     # prints per-block state; names any MISSING artifact
node --check <extracted js> # syntax
```

The render tests live in the session transcript rather than the repo — if you want them
committed as a permanent check, say so and they can move into `tests/`.
