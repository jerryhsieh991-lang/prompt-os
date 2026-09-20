/* Independent verifier for the client-side analysis engine.
 *
 * SITE.md claimed "a build-time browser check confirms exact parity" between the
 * Python engine in build_site.py and its JavaScript mirror in assets/app.js. No such
 * check existed. This is it, and it runs in CI with no browser required.
 *
 *   1. every rule regex exported by analysis_rules() must compile as a JS RegExp
 *   2. for every corpus prompt, the JS engine's verifier_type and pattern set must
 *      equal what the Python build wrote into site/data/prompts.json
 *
 * Usage: node tools/check_js.mjs   (after python3 build_site.py)
 */
import fs from 'fs';
import vm from 'vm';

const SITE = 'site';
const js = fs.readFileSync(`${SITE}/assets/app.js`, 'utf8');
const prompts = JSON.parse(fs.readFileSync(`${SITE}/data/prompts.json`, 'utf8'));

const m = js.match(/window\.PROMPTOS_RULES=(\{.*?\});/s);
if (!m) { console.error('FAIL: PROMPTOS_RULES not injected into app.js'); process.exit(1); }
const rules = JSON.parse(m[1]);

const failures = [];

// ---- 1. regex dialect ------------------------------------------------------
for (const [role, src] of rules.anchors) {
  try { new RegExp(src, 'gi'); }
  catch (e) { failures.push(`anchor regex '${role}' is not valid JS: ${e.message}`); }
}
try { new RegExp(rules.explicitVerifier, 'i'); }
catch (e) { failures.push(`explicitVerifier regex is not valid JS: ${e.message}`); }

// ---- 2. engine parity over the whole corpus --------------------------------
const i = js.indexOf('var PROMPTOS = (function () {');
const engine = js.slice(i, js.indexOf('\n})();', i) + 6);
const pescStart = js.indexOf('function pesc');
const pescSrc = js.slice(pescStart, js.indexOf('\n}\n', pescStart) + 3);
const sandbox = { window: { PROMPTOS_RULES: rules, console }, console };
vm.createContext(sandbox);
vm.runInContext(`${pescSrc}\n${engine}\nglobalThis.__engine = PROMPTOS;`, sandbox);
const engineApi = sandbox.__engine;

if (!engineApi) {
  failures.push('analysis engine returned null on healthy rules (guard swallowed a real error)');
} else {
  for (const p of prompts) {
    const a = engineApi.analyze(p.prompt_text, { model: p.model || '', fk: p.family_key });
    if (a.verifier !== p.verifier_type) {
      failures.push(`${p.id}: verifier JS='${a.verifier}' vs Python='${p.verifier_type}'`);
    }
    const jsPats = [...a.patterns].map(k => engineApi.PNAME[k] || k).sort();
    const pyPats = [...p.patterns].sort();
    if (JSON.stringify(jsPats) !== JSON.stringify(pyPats)) {
      failures.push(`${p.id}: patterns JS=[${jsPats}] vs Python=[${pyPats}]`);
    }
  }
}

if (failures.length) {
  console.error(`PARITY FAILED — ${failures.length} mismatch(es):`);
  for (const f of failures.slice(0, 20)) console.error('  -', f);
  if (failures.length > 20) console.error(`  ... and ${failures.length - 20} more`);
  process.exit(1);
}
console.log(`parity OK: ${prompts.length} prompts, verifier_type + pattern set identical in Python and JS`);
