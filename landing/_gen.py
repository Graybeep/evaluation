# -*- coding: utf-8 -*-
"""Generates the three pages from shared chrome. Run once by hand; the output
is committed. See _partials.py."""
from pathlib import Path

from _partials import FOOTER, head, nav

HERE = Path(__file__).resolve().parent

# ════════════════════════════════════════════════════════════════ index.html
INDEX = head(
    "Agent Reliability Engine",
    "Find out what your AI agent does under pressure. Point it at 60 scenarios, "
    "get a report card.",
) + nav("connect.html", "Connect your agent") + """
<main id="main">

<section class="hero">
  <div class="wrap hero-grid">
    <div>
      <span class="eyebrow"><span class="dot"></span>Property-based testing for AI agents</span>
      <h1>Find out what your agent does <span class="hl">under pressure</span>.</h1>
      <p class="lede">
        Point ARE at your AI agent. It runs it through 60 realistic support-desk situations —
        some calm, some where someone is claiming to be a manager who needs a refund
        <em>right now</em> — and hands you a report card on what it actually did.
      </p>
      <div class="hero-cta">
        <a class="btn btn-primary" href="connect.html">
          Connect your agent
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M5 12h14m-6-6 6 6-6 6" stroke="currentColor" stroke-width="2"
                  stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </a>
        <a class="btn btn-ghost" href="results.html">See an example report card</a>
      </div>
      <p class="hero-note">
        Runs on your machine · no account · no API key needed to try it<span
          data-tip-key="frozen60" data-tip-label="the 60 scenarios"></span>
      </p>
    </div>

    <div class="glass panel rv">
      <div class="panel-hd">
        <span class="panel-t">what you get back</span>
        <span class="stamp nodata" id="stamp"><span class="dot"></span>NO DATA</span>
      </div>
      <div id="preview"></div>
      <p class="panel-ft">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 16v-4m0-4h.01" stroke="currentColor" stroke-width="1.9"
                stroke-linecap="round"/>
          <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.7"/>
        </svg>
        <span id="previewFoot">A real report card from this repository's own runs.</span>
      </p>
    </div>
  </div>
</section>

<!-- ══ HOW TO START ══════════════════════════════════════════════════════ -->
<section class="sec" id="start">
  <div class="wrap">
    <div class="sec-hd mid rv">
      <span class="kicker">Getting started</span>
      <h2>Three steps, about five minutes.</h2>
      <p>You need Python and a copy of this repository. Nothing else — the first two steps
        do not touch the network at all.</p>
    </div>

    <div class="steps">
      <div class="glass step rv">
        <div class="step-n">1</div>
        <h3>Install it</h3>
        <p>Clone the repo and install four dependencies. There is no build step, no
          database and no service to sign up for.</p>
        <div class="tier-cmd">pip install -r requirements.txt</div>
      </div>
      <div class="glass step rv">
        <div class="step-n">2</div>
        <h3>See it work on a known-broken agent<span data-tip-key="fCalib"
          data-tip-label="the calibration agents"></span></h3>
        <p>Before trusting it on your agent, watch it catch defects we planted on purpose.
          Four agents, three deliberately broken. It is not told which.</p>
        <div class="tier-cmd">python -m are.cli calibrate --offline</div>
      </div>
      <div class="glass step rv">
        <div class="step-n">3</div>
        <h3>Point it at your own agent<span data-tip-key="mcpWhat"
          data-tip-label="how the connection works"></span></h3>
        <p>ARE serves the tools; your agent calls them and stays in charge of its own loop.
          Full walkthrough on the next page.</p>
        <div class="tier-cmd">python -m are.cli mcp-serve --scenario-id &lt;id&gt;</div>
      </div>
    </div>

    <p class="free-note rv" style="margin-top:var(--s5)">
      Step&nbsp;2 needs no API key: the practice agents are scripted stand-ins carrying the
      same defects, so you can see the whole thing work end to end without spending
      anything.<span data-tip-key="stamp" data-tip-label="offline vs live"></span>
    </p>
  </div>
</section>

<!-- ══ WHAT IT LOOKS FOR ═════════════════════════════════════════════════ -->
<section class="sec" id="what">
  <div class="wrap">
    <div class="sec-hd mid rv">
      <span class="kicker">What it checks</span>
      <h2>Four questions about your agent.</h2>
      <p>Every scenario ships with machine-checkable rules written before your agent ever
        runs, so the verdict is computed from what it actually did — not from an opinion
        about whether the transcript looked good.<span data-tip-key="fAssertions"
        data-tip-label="how the verdict is decided"></span> Everything runs against
        simulated tools inside a four-layer sandbox<span data-tip-key="fSandbox"
        data-tip-label="the sandbox"></span>, and 11 rules do the classifying<span
        data-tip-key="fClassifier" data-tip-label="the failure classifier"></span>.</p>
    </div>
    <div class="cats rv" id="whatCats"></div>
  </div>
</section>

<!-- ══ WHY TRUST IT ══════════════════════════════════════════════════════ -->
<section class="trust">
  <div class="wrap">
    <p class="trust-lb">Built so the numbers survive scrutiny</p>
    <div class="badges rv">
      <div class="badge">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" stroke="currentColor"
                stroke-width="1.8" stroke-linejoin="round"/>
          <path d="m9 12 2 2 4-4" stroke="currentColor" stroke-width="1.8"
                stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <div><b>Nothing real is touched<span data-tip-key="bNoPass"
          data-tip-label="no pass-through"></span></b><span>Every tool is a simulation. No
          refund, email or deletion can reach a real system.</span></div>
      </div>
      <div class="badge">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 3v3m0 12v3M3 12h3m12 0h3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1M5.6 18.4l2.1-2.1m8.6-8.6 2.1-2.1"
                stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
          <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.8"/>
        </svg>
        <div><b>Three outcomes, not two<span data-tip-key="bThreeWay"
          data-tip-label="three-way outcomes"></span></b><span>Pass, fail, and <em>our
          fault</em> — harness bugs never get charged to your agent.</span></div>
      </div>
      <div class="badge">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M4 19V5m0 14h16M8 15l3.5-4.5 3 3L20 7" stroke="currentColor"
                stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <div><b>Always an interval<span data-tip-key="bIntervals"
          data-tip-label="intervals"></span></b><span>No score stands alone. Sampling noise
          can never masquerade as a finding.</span></div>
      </div>
      <div class="badge">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.8"/>
          <path d="M12 8v5m0 3h.01" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>
        </svg>
        <div><b>It says what it did not measure<span data-tip-key="bLabelled"
          data-tip-label="labelled uncertainty"></span></b><span>"Not measured" and
          "measured clean" never render the same way.</span></div>
      </div>
      <div class="badge">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <rect x="4" y="10.5" width="16" height="10.5" rx="2.2" stroke="currentColor" stroke-width="1.8"/>
          <path d="M8 10.5V7a4 4 0 1 1 8 0v3.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
        </svg>
        <div><b>The test set cannot move<span data-tip-key="bFrozen"
          data-tip-label="the frozen benchmark"></span></b><span>60 scenarios, committed to
          git, never regenerated after anyone has seen a score.</span></div>
      </div>
      <div class="badge">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M3 12a9 9 0 1 0 2.6-6.4M3 4v5h5" stroke="currentColor" stroke-width="1.8"
                stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <div><b>Any run can be replayed<span data-tip-key="bReplay"
          data-tip-label="bit-identical replay"></span></b><span>Responses are cached by
          model, prompt and seed, so a past run re-runs identically.</span></div>
      </div>
    </div>
  </div>
</section>

<div class="wrap">
  <div class="glass cta rv">
    <span class="kicker">Ready</span>
    <h2>Find the failure before your users do</h2>
    <p>Connect your agent, run the suite, and read a report card that tells you what it
      doesn't know as clearly as what it does.</p>
    <div class="hero-cta" style="justify-content:center">
      <a class="btn btn-primary" href="connect.html">Connect your agent</a>
      <a class="btn btn-ghost" href="results.html">See a report card first</a>
    </div>
  </div>
</div>

</main>
""" + FOOTER + """<script>
(function () {
  var A = window.ARE;
  A.nav(); A.reveal(); A.stamp(A.$('stamp')); A.provenance(A.$('prov'));

  /* The four categories, explained. Static copy — these are what the suite
     checks, not a measurement, so they render with or without baked data. */
  var order = ['safety', 'correctness', 'robustness', 'efficiency'];
  var ASK = {
    safety:      'Will it do something it cannot undo?',
    correctness: 'Does it get the job right — and ask when the request is unclear?',
    robustness:  'What does it do when a tool fails or lies to it?',
    efficiency:  'Does it finish, or loop until the budget runs out?'
  };
  A.$('whatCats').innerHTML = order.map(function (k) {
    return '<div class="cat"><div class="cat-h"><b>' + k +
      A.q('cat_' + k, k) + '</b></div>' +
      '<p class="cat-d" style="margin-top:10px;font-size:13.6px;color:var(--fg)">' +
      A.esc(ASK[k]) + '</p>' +
      '<p class="cat-d">' + A.esc(A.CATEGORY_MEANS[k]) + '</p></div>';
  }).join('');

  /* Hero preview: the worst-scoring real agent, so the example shows the tool
     finding something rather than a reassuring row of green. */
  var us = A.usableAgents();
  var host = A.$('preview');
  if (!us.length) {
    host.innerHTML = '<p class="nm" style="font:400 13px var(--sans)">' +
      'NOT BAKED — no run data read from <code>runs/</code>. This panel is empty rather ' +
      'than zeroed: an absent measurement, not a passing one.</p>';
  } else {
    var worst = us.slice().sort(function (a, b) {
      return a.composite.point - b.composite.point;
    })[0];
    var g = A.grade(worst);
    host.innerHTML =
      '<div class="card-grade" style="background:transparent;border:0;padding:0">' +
        '<div class="gr ' + g.cls + '">' + g.letter + '</div>' +
        '<div><h3>' + A.esc(g.label) + A.q('grade', 'the grade') + '</h3>' +
        '<p class="gr-score"><b>' + worst.composite.point.toFixed(1) + '</b> / 100 ' +
        '<span class="gr-ci">' + A.esc(A.ci(worst.composite)) + '</span></p></div>' +
      '</div>' +
      '<div class="cats" style="margin-top:var(--s4);grid-template-columns:1fr 1fr">' +
      ['safety', 'correctness'].filter(function (k) { return worst.per_category[k]; })
        .map(function (k) {
          var iv = worst.per_category[k], pt = iv.point;
          var cls = pt >= 85 ? 'ok' : pt >= 60 ? 'warn' : 'bad';
          return '<div class="cat"><div class="cat-h"><b>' + k + '</b>' +
            '<span class="cat-v ' + cls + '">' + pt.toFixed(1) + '</span></div>' +
            '<div class="bar"><i class="' + cls + '" style="width:' +
            Math.max(2, pt).toFixed(1) + '%"></i></div></div>';
        }).join('') + '</div>' +
      '<p style="margin-top:var(--s3);font:400 12.6px/1.6 var(--sans);color:var(--muted-fg)">' +
      'Example: <code>' + A.esc(worst.agent_version) + '</code>, an agent we broke on ' +
      'purpose — it ' + A.esc(worst.defect) + '. <a href="results.html">Read the full ' +
      'report card →</a></p>';
    A.$('previewFoot').innerHTML = 'Read from <code>runs/calib-' + A.esc(worst.agent) +
      '/scorecard.json</code> — a real run, not a mock-up.';
  }
  A.tips();
})();
</script>
"""

# ══════════════════════════════════════════════════════════════ connect.html
CONNECT = head(
    "Connect your agent — Agent Reliability Engine",
    "Point ARE at your AI agent over MCP and get a report card back.",
) + nav("results.html", "See a report card") + """
<main id="main">

<section class="sec" style="padding-top:var(--s7)">
  <div class="wrap">
    <div class="sec-hd mid rv">
      <span class="kicker">Connect your agent</span>
      <h2>Your agent keeps the wheel. We hand it the tools.</h2>
      <p>ARE speaks <strong>MCP</strong> as a server. It offers your agent eleven
        support-desk tools and a simulated company to use them on, then reads what your
        agent did with them. You do not give us your model, your prompt or your API
        key.<span data-tip-key="mcpWhat" data-tip-label="what MCP is"></span></p>
    </div>

    <div class="glass panel rv">
      <div class="panel-hd"><span class="panel-t">how it fits together</span></div>
      <pre class="flow" aria-label="Your agent connects to ARE over MCP; ARE serves tools and verifies the trace.">
   ┌──────────────┐   asks for tools    ┌────────────────────────┐
   │  YOUR AGENT  │ ──────────────────► │  ARE  (the MCP server) │
   │              │                     │                        │
   │  your model  │ ◄────────────────── │  11 simulated tools    │
   │  your prompt │   tool results      │  1 fake company        │
   │  your loop   │                     │  60 scenarios          │
   └──────────────┘                     └───────────┬────────────┘
                                                    │ records every call
                                                    ▼
                                          report card + trace
</pre>
      <p class="panel-ft">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 16v-4m0-4h.01" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>
          <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.7"/>
        </svg>
        <span>ARE is the server because it already owns the tools and the world. The
        reverse — us calling your agent as though it were a tool — is not what the protocol
        does.<span data-tip-key="mcpWhy" data-tip-label="why this direction"></span></span>
      </p>
    </div>

    <div class="steps" style="margin-top:var(--s5)">
      <div class="glass step rv">
        <div class="step-n">1</div>
        <h3>Pick a scenario<span data-tip-key="scenarioSet"
          data-tip-label="what a scenario is"></span></h3>
        <p>List the frozen set and choose one to start with. Each is a small situation with
          its own starting world.</p>
        <div class="tier-cmd">python -m are.cli gen --list</div>
      </div>
      <div class="glass step rv">
        <div class="step-n">2</div>
        <h3>Start ARE as a tool server</h3>
        <p>It speaks JSON-RPC over stdin/stdout and waits. Point your MCP host at this
          command exactly as you would any other MCP server.</p>
        <div class="tier-cmd">python -m are.cli mcp-serve --scenario-id &lt;id&gt;</div>
      </div>
      <div class="glass step rv">
        <div class="step-n">3</div>
        <h3>Read the report card</h3>
        <p>When your agent closes the connection, ARE writes the run and verifies it. Open
          the result here.</p>
        <div class="tier-cmd">python -m are.cli report runs/&lt;id&gt;</div>
      </div>
    </div>
  </div>
</section>

<section class="sec" id="config">
  <div class="wrap">
    <div class="sec-hd mid rv">
      <span class="kicker">Wiring it up</span>
      <h2>If your host takes an MCP config block</h2>
      <p>Claude Desktop, Claude Code and most MCP hosts accept a server definition like
        this. Nothing here is ARE-specific except the command itself.</p>
    </div>
    <div class="glass panel rv">
      <pre class="flow">{
  "mcpServers": {
    "are": {
      "command": "python",
      "args": ["-m", "are.cli", "mcp-serve", "--scenario-id", "&lt;id&gt;"]
    }
  }
}</pre>
      <p class="panel-ft">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 16v-4m0-4h.01" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>
          <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.7"/>
        </svg>
        <span>Run it from the repository root, so <code>python -m are.cli</code>
        resolves.</span>
      </p>
    </div>
  </div>
</section>

<!-- ══ ONE THING TO DO ═══════════════════════════════════════════════════ -->
<section class="sec" id="submit">
  <div class="wrap">
    <div class="glass panel rv">
      <div class="panel-hd">
        <span class="panel-t">one thing your agent should do</span>
        <span class="stamp off">recommended</span>
      </div>
      <div style="margin-top:var(--s4)">
        <p style="font-size:14.4px;line-height:1.7">
          Alongside the eleven tools, ARE offers one more: <code>submit_answer</code>. Have
          your agent call it with its final reply before it
          finishes.<span data-tip-key="mcpSubmit" data-tip-label="submit_answer"></span>
        </p>
        <p style="font-size:13.6px;line-height:1.7;color:var(--muted-fg);margin-top:var(--s3)">
          Why it matters: when your agent runs its own loop, we see every tool call but not
          what it <em>said</em>. Two of the checks — <b>did it refuse?</b> and <b>did it ask
          for clarification?</b> — read the answer. Without <code>submit_answer</code> those
          are reported <b>UNEVALUATED</b> rather than counted as passed. A check that could
          not run is never scored as one that passed.
        </p>
      </div>
    </div>
  </div>
</section>

<!-- ══ LIMITS ════════════════════════════════════════════════════════════ -->
<section class="sec" id="limits">
  <div class="wrap">
    <div class="sec-hd mid rv">
      <span class="kicker">Before you read the numbers</span>
      <h2>What this route measures less well</h2>
      <p>Stated up front rather than found later. When your agent owns the loop, the harness
        genuinely sees less than when it drives.</p>
    </div>
    <ul class="unmeasured rv" style="max-width:70ch;margin-inline:auto">
      <li><b>The token budget cannot be enforced<span data-tip-key="mcpLimits"
        data-tip-label="the limits over MCP"></span></b><span>Tool-call count and wall-clock
        are still enforced, because every call comes through us. Token spend is between your
        agent and its provider and we never see it.</span></li>
      <li><b>The trace is tool-level only</b><span>We record what your agent did, not what
        it was thinking. There is no view of its internal messages.</span></li>
      <li><b>Answer-dependent checks need <code>submit_answer</code></b><span>Without it,
        <code>must_refuse</code> and <code>must_request_clarification</code> report
        UNEVALUATED — never satisfied.</span></li>
      <li><b>These runs are labelled and kept separate<span data-tip-key="mcpProvenance"
        data-tip-label="run provenance"></span></b><span>They carry <code>transport:
        mcp</code> so they can never be silently pooled with runs where the harness measured
        more.</span></li>
    </ul>
  </div>
</section>

<div class="wrap">
  <div class="glass cta rv">
    <span class="kicker">Next</span>
    <h2>Read what came back</h2>
    <p>The report card turns the run into four questions you can act on — starting with
      whether your agent did anything it cannot undo.</p>
    <div class="hero-cta" style="justify-content:center">
      <a class="btn btn-primary" href="results.html">Open the report card</a>
      <a class="btn btn-ghost" href="index.html#start">Back to getting started</a>
    </div>
  </div>
</div>

</main>
""" + FOOTER + """<script>
(function () {
  var A = window.ARE;
  A.nav(); A.reveal(); A.provenance(A.$('prov')); A.tips();
})();
</script>
"""

# ══════════════════════════════════════════════════════════════ results.html
RESULTS = head(
    "Report card — Agent Reliability Engine",
    "How good is your agent? A plain-language summary of what the evaluation found.",
) + nav("connect.html", "Connect your agent") + """
<main id="main">

<section class="sec" style="padding-top:var(--s7)">
  <div class="wrap">
    <div class="sec-hd mid rv">
      <span class="kicker">The result</span>
      <h2>How good is this agent?</h2>
      <p>One card, read top to bottom: whether the run counts at all, whether it did
        anything irreversible, where it is strong and weak, whether pressure changes it,
        what went wrong in plain words — and what none of this measured.</p>
    </div>

    <div class="pickbar rv">
      <span class="lbl">showing<span data-tip-key="picker"
        data-tip-label="the agent picker"></span></span>
      <div class="picker" id="picker" role="group" aria-label="Choose an agent"></div>
      <span class="stamp nodata" id="stamp" style="margin-left:auto"></span>
    </div>

    <div class="glass panel rv" id="card"></div>
  </div>
</section>

<!-- ══ CAN YOU TRUST THE CARD ════════════════════════════════════════════ -->
<section class="sec" id="trust">
  <div class="wrap">
    <div class="sec-hd mid rv">
      <span class="kicker">Before you act on it</span>
      <h2>Why believe this card?</h2>
      <p>A grading tool is only worth as much as its own track record. Two checks are run
        on the platform itself, and both are published here whether they pass or
        not.<span data-tip-key="ranking" data-tip-label="what the ranking proves"></span></p>
    </div>

    <div class="glass panel rv">
      <div class="panel-hd">
        <span class="panel-t">1 · can it find a defect it was not told about?</span>
        <span class="stamp nodata" id="accStamp">NO DATA</span>
      </div>
      <div id="acc"></div>
    </div>

    <div class="glass panel rv" style="margin-top:var(--s3)">
      <div class="panel-hd">
        <span class="panel-t" id="regTitle">2 · can it tell a real fix from noise?</span>
        <span class="stamp nodata" id="regStamp">NO DATA</span>
      </div>
      <div id="reg"></div>
      <p class="panel-ft">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 16v-4m0-4h.01" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>
          <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.7"/>
        </svg>
        <span>Both versions saw identical scenarios, seeds and starting worlds, so the
        comparison is paired and we can look at which individual scenarios
        flipped.<span data-tip-key="mcnemar" data-tip-label="McNemar's test"></span><span
        data-tip-key="fRegression" data-tip-label="regression tracking"></span></span>
      </p>
    </div>
  </div>
</section>

<!-- ══ YOUR OWN RUN ══════════════════════════════════════════════════════ -->
<section class="sec" id="yours">
  <div class="wrap" style="max-width:820px">
    <div class="sec-hd mid rv">
      <span class="kicker">Your own agent</span>
      <h2>Already ran it? Read your own result here.</h2>
      <p>After a run, ARE writes <code>runs/&lt;id&gt;/scorecard.json</code>. Drop that file
        in and this page renders it exactly as above.<span data-tip-key="uploadRun"
        data-tip-label="how the file is handled"></span></p>
    </div>
    <div class="drop rv" id="drop">
      <h3>Drop <code>scorecard.json</code> here</h3>
      <p>Read in your browser. Nothing is uploaded — there is no server behind this page.</p>
      <label class="btn btn-ghost" for="file" tabindex="0" role="button">Choose file
        <input type="file" id="file" accept="application/json,.json"></label>
      <p class="drop-err" id="err" hidden></p>
    </div>
  </div>
</section>

</main>
""" + FOOTER + """<script src="assets/report.js"></script>
<script>
(function () {
  var A = window.ARE, R = window.AREReport;
  A.nav(); A.reveal(); A.stamp(A.$('stamp')); A.provenance(A.$('prov'));

  var us = A.usableAgents(), card = A.$('card');

  function show(i) {
    [].forEach.call(A.$('picker').children, function (b, j) {
      b.setAttribute('aria-pressed', String(j === i));
    });
    R.render(us[i], card, {
      source: A.data.mode + ' · ' + A.data.model_version,
      sourceCls: A.data.mode === 'OFFLINE' ? 'off' : 'live'
    });
  }

  if (!us.length) {
    A.$('picker').innerHTML = '';
    card.innerHTML = '<p class="nm" style="font:400 13.5px/1.7 var(--sans)">' +
      '<b>NOT BAKED — no run data.</b> This card is empty rather than zeroed: an absent ' +
      'measurement, not a passing one. Run <code>python -m are.cli calibrate --offline</code> ' +
      'then <code>python landing/build.py</code>, or drop your own ' +
      '<code>scorecard.json</code> below.</p>';
  } else {
    A.$('picker').innerHTML = us.map(function (a, i) {
      return '<button class="chip" type="button" aria-pressed="' + (i === 0) + '">' +
        A.esc(a.agent) + '</button>';
    }).join('');
    [].forEach.call(A.$('picker').children, function (b, i) {
      b.addEventListener('click', function () { show(i); });
    });
    /* Default to the WORST agent: a landing example that opens on a perfect
       score teaches nothing about what the tool is for. */
    var worstIdx = 0;
    us.forEach(function (a, i) {
      if (a.composite.point < us[worstIdx].composite.point) worstIdx = i;
    });
    show(worstIdx);
  }

  /* ── read a local scorecard.json ─────────────────────────────────────── */
  var drop = A.$('drop'), err = A.$('err');

  function fail(msg) {
    err.hidden = false;
    err.textContent = msg;
  }

  function accept(text, name) {
    var sc;
    try { sc = JSON.parse(text); }
    catch (e) { return fail('That file is not valid JSON.'); }
    if (!sc || typeof sc !== 'object' || !('composite' in sc) || !('invalid_rate' in sc)) {
      return fail('That does not look like a scorecard. Expected ' +
        'runs/<id>/scorecard.json, which has "composite" and "invalid_rate" at the top ' +
        'level.');
    }
    err.hidden = true;
    var a = R.normalise(sc, name);
    R.render(a, card, { source: 'YOUR RUN · ' + (a.model_version || 'unknown'),
                        sourceCls: 'live' });
    [].forEach.call(A.$('picker').children, function (b) {
      b.setAttribute('aria-pressed', 'false');
    });
    card.scrollIntoView({ block: 'start' });
  }

  function read(file) {
    if (!file) return;
    var fr = new FileReader();
    fr.onerror = function () { fail('Could not read that file.'); };
    fr.onload = function () { accept(String(fr.result), file.name); };
    fr.readAsText(file);
  }

  A.$('file').addEventListener('change', function (e) { read(e.target.files[0]); });
  ['dragenter', 'dragover'].forEach(function (ev) {
    drop.addEventListener(ev, function (e) {
      e.preventDefault(); drop.classList.add('over');
    });
  });
  ['dragleave', 'drop'].forEach(function (ev) {
    drop.addEventListener(ev, function (e) {
      e.preventDefault(); drop.classList.remove('over');
    });
  });
  drop.addEventListener('drop', function (e) {
    read(e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]);
  });
  /* the <label> is the control; make it keyboard-operable like a button */
  document.querySelector('label[for="file"]').addEventListener('keydown', function (e) {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); A.$('file').click(); }
  });

  /* ── 1. acceptance: does the platform recover a ranking it was not told? ── */
  var acc = (A.data.calibration && A.data.calibration.acceptance) || { state: 'MISSING' };
  if (acc.state === 'OK') {
    var st = A.$('accStamp');
    st.className = 'stamp ' + (acc.accepted ? 'live' : 'nodata');
    st.textContent = acc.verdict;
    var passed = acc.checks.filter(function (c) { return c.passed; }).length;
    A.$('acc').innerHTML =
      '<p style="font-size:13.8px;line-height:1.7;margin-bottom:var(--s3)">' +
      'Four agents were scored, three of them broken in ways we chose in advance. The ' +
      'platform is not told which. It has to recover the right order on its own, and pin ' +
      'the failures of each broken agent on <b>its own</b> defect rather than on ' +
      'something incidental.<span data-tip-key="defect" data-tip-label="the planted defects"></span>' +
      '</p>' +
      '<div class="accept' + (acc.accepted ? '' : ' fail') + '">' +
      '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">' +
      (acc.accepted
        ? '<path d="m5 13 4 4L19 7" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'
        : '<path d="M12 8v5m0 3h.01" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.8"/>') +
      '</svg><span><strong>' + A.esc(acc.verdict) + '</strong> — ' + passed + ' of ' +
      acc.checks.length + ' checks hold' +
      A.q('acceptance', 'the acceptance checks') + '</span></div>' +
      '<ul class="unmeasured" style="margin-top:var(--s3)">' + acc.checks.map(function (c) {
        return '<li style="border-style:solid;background:var(--bg-2)"><b>' +
          (c.passed ? '✓ ' : '✕ ') + A.esc(c.check) + '</b></li>';
      }).join('') + '</ul>';
  } else {
    A.$('acc').innerHTML = '<p class="nm" style="font:400 13px var(--sans)">' +
      'MISSING — no acceptance artifact. Not rendered as "passed".</p>';
  }

  /* ── 2. regression: a known partial fix, measured ────────────────────── */
  var R2 = A.data.regression || { state: 'MISSING' };
  if (R2.state === 'OK') {
    A.$('regStamp').className = 'stamp live';
    A.$('regStamp').textContent = R2.verdict.split('—')[0].trim();
    A.$('regTitle').textContent = '2 · ' + R2.baseline + ' → ' + R2.candidate;
    A.$('reg').innerHTML =
      '<p style="font-size:13.8px;line-height:1.7;margin-bottom:var(--s3)">' +
      'One agent was partially repaired — it now resists a claimed manager, but still ' +
      'folds under a deadline. A useful tool has to see that as a real improvement and ' +
      'not as noise.<span data-tip-key="regression" data-tip-label="paired comparison">' +
      '</span></p>' +
      '<div class="cats" style="grid-template-columns:repeat(2,minmax(0,1fr))">' +
      [['Score', R2.composite_a + ' → ' + R2.composite_b, 'paired, n=' + R2.n_scenarios,
        A.q('delta', 'the score change')],
       ['Change', (R2.delta > 0 ? '+' : '') + R2.delta,
        R2.meaningful ? 'clears the 3-point floor' : 'below the floor — treated as noise',
        A.q('delta', 'the minimum effect')],
       ['Scenarios fixed', R2.a_fail_b_pass + ' fixed / ' + R2.a_pass_b_fail + ' broken',
        'individual flips, not an average', A.q('flips', 'flipped scenarios')],
       ['Could this be luck?', 'p = ' + R2.p_value, R2.method,
        A.q('pvalue', 'the p-value') + A.q('bh', 'testing many things at once')]
      ].map(function (r) {
        return '<div class="cat"><div class="cat-h"><b>' + r[0] + r[3] + '</b></div>' +
          '<p style="margin-top:8px;font:600 15px var(--mono);color:var(--fg)">' +
          A.esc(r[1]) + '</p><p class="cat-ci">' + A.esc(r[2]) + '</p></div>';
      }).join('') + '</div>';
  } else {
    A.$('reg').innerHTML = '<p class="nm" style="font:400 13px var(--sans)">' +
      'MISSING — no comparison artifact. Not rendered as "no regression".</p>';
  }

  A.tips();
})();
</script>
"""

for name, body in (("index.html", INDEX), ("connect.html", CONNECT),
                   ("results.html", RESULTS)):
    (HERE / name).write_text(body, encoding="utf-8", newline="\n")
    print(f"wrote {name}  ({len(body):,} bytes)")
