/* Render harness for the report card — run with:  node landing/render_check.js
 *
 * A DOM shim thin enough to run common.js + report.js and capture the HTML the
 * report card produces, so the render is asserted rather than eyeballed. This
 * exists because the two rules that matter most are invisible in a screenshot:
 * an unreportable run must print NO score, and any CRITICAL finding must cap
 * the grade. Both are checked below against the real baked data.
 *
 * Wired into pytest as tests/test_landing_site.py::test_report_card_renders,
 * which skips loudly when node is unavailable.
 */
/* Minimal DOM shim: enough to run common.js + report.js and capture the HTML
   the report card produces, so the render is verified rather than eyeballed. */
const fs = require('fs');
const path = require('path');
const L = path.resolve(__dirname);   // this file lives in landing/

function el() {
  return {
    innerHTML: '', textContent: '', className: '', hidden: false, children: [],
    style: {}, classList: { add() {}, remove() {}, contains() { return false; } },
    setAttribute() {}, getAttribute() { return null; }, removeAttribute() {},
    addEventListener() {}, appendChild() {}, scrollIntoView() {},
    querySelector() { return el(); }, querySelectorAll() { return []; },
    replaceWith() {}, remove() {}, parentNode: { replaceChild() {} }
  };
}

global.window = {};
global.document = {
  getElementById: () => el(),
  querySelector: () => el(),
  querySelectorAll: () => [],
  createElement: () => el(),
  addEventListener() {}, body: el(), documentElement: el()
};
global.location = { pathname: '/results.html' };
global.matchMedia = () => ({ matches: false });
global.IntersectionObserver = function () {
  return { observe() {}, unobserve() {} };
};
global.FileReader = function () {};
global.window.matchMedia = global.matchMedia;

function load(f) { (0, eval)(fs.readFileSync(path.join(L, f), 'utf8')); }

load('assets/data.js');
load('assets/common.js');
load('assets/report.js');

const A = global.window.ARE, R = global.window.AREReport;
const agents = A.usableAgents();

console.log('data baked   :', A.data.baked);
console.log('agents usable:', agents.length);
console.log('');

let fail = 0;
function check(name, cond) {
  if (!cond) { fail++; console.log('  FAIL  ' + name); }
  else console.log('  ok    ' + name);
}

for (const a of agents) {
  const g = A.grade(a);
  const host = el();
  R.render(a, host, { source: 'TEST' });
  const h = host.innerHTML;
  const crit = A.criticalModes(a).length;

  console.log(`── ${a.agent_version}  composite ${a.composite.point.toFixed(1)} ` +
              `→ grade ${g.letter}${g.capped ? ' (capped)' : ''}  critical=${crit}`);

  check('renders a grade block', h.includes('card-grade'));
  check('shows the composite number', h.includes(a.composite.point.toFixed(1)));
  check('shows an interval', h.includes('CI [') || h.includes('n='));
  check('has the unmeasured section', h.includes('unmeasured'));
  check('states flake measurability in words',
        h.includes('not measured') || h.includes('quarantined'));
  check('safety block present',
        h.includes('safe-ok') || h.includes('safe-bad'));
  if (crit > 0) {
    check('critical -> safety warning block', h.includes('safe-bad'));
    check('critical -> grade capped at D or below', 'DF'.includes(g.letter));
  } else {
    check('no critical -> clean safety block', h.includes('safe-ok'));
  }
  check('no raw [object Object]', !h.includes('[object Object]'));
  check('no undefined leaked', !h.includes('undefined'));
  console.log('');
}

/* the two rules that must hold regardless of data */
console.log('── gate behaviour');
const unrep = { state: 'OK', reportable: false, invalid_rate: 12.5,
                composite: { point: 40, low: 30, high: 50, n: 60 }, modes: [],
                per_category: {}, pressure: {}, n_scenarios: 60, n_runs: 180,
                flaky_measurable: false, judge_used: false, agent: 'x' };
const gu = A.grade(unrep);
check('unreportable run gets NO grade', gu.letter === '—' && !gu.reportable);
const hostU = el();
R.render(unrep, hostU, {});
check('unreportable card says NOT REPORTABLE', hostU.innerHTML.includes('NOT REPORTABLE'));
check('unreportable card shows no composite score',
      !hostU.innerHTML.includes('/ 100 composite'));

const capped = { state: 'OK', reportable: true, invalid_rate: 0,
                 composite: { point: 96, low: 92, high: 99, n: 60 },
                 modes: [{ mode: 'DESTRUCTIVE_ACTION', severity: 'CRITICAL',
                           scenarios_affected: 1 }],
                 per_category: {}, pressure: {}, n_scenarios: 60, n_runs: 180,
                 flaky_measurable: true, judge_used: true, agent: 'y' };
check('96 + one CRITICAL is capped to D', A.grade(capped).letter === 'D');
check('… and the cap is explained, not silent',
      (function () { const h = el(); R.render(capped, h, {});
                     return h.innerHTML.includes('capped'); })());

console.log('');
console.log(fail === 0 ? 'ALL CHECKS PASSED' : fail + ' CHECK(S) FAILED');
process.exit(fail === 0 ? 0 : 1);
