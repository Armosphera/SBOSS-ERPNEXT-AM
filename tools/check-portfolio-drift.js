#!/usr/bin/env node
/**
 * Portfolio drift guard.
 * Verifies that the set of repos in expected-repos.json is exactly the set
 * present in the armosphera GitHub org that match our naming convention.
 *
 * Exits 0 if everything matches; exits 1 with details otherwise.
 *
 * Usage: node tools/check-portfolio-drift.js
 */
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const EXPECTED = JSON.parse(fs.readFileSync(path.join(ROOT, '.orchestration/expected-repos.json'), 'utf8'));

let actualNames = [];
try {
  const json = execSync('gh repo list armosphera --json name --limit 200', { encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] });
  const data = JSON.parse(json);
  actualNames = data.map(r => r.name);
} catch (e) {
  console.error('ERROR: could not list armosphera repos via gh. Are you authed?');
  console.error(e.message);
  process.exit(2);
}

const expectedNames = EXPECTED.repos.map(r => r.name);
const missing = expectedNames.filter(n => !actualNames.includes(n));
const extra = actualNames.filter(n => !expectedNames.includes(n) && n.startsWith('SBOSS-'));

if (missing.length === 0 && extra.length === 0) {
  console.log(`OK: portfolio matches expected-repos.json (${expectedNames.length} repo(s))`);
  process.exit(0);
}

if (missing.length > 0) {
  console.error('ERROR: expected repos missing from armosphera org:');
  missing.forEach(n => console.error('  - ' + n));
}
if (extra.length > 0) {
  console.error('ERROR: unexpected SBOSS-* repos in armosphera org:');
  extra.forEach(n => console.error('  - ' + n));
}
process.exit(1);
