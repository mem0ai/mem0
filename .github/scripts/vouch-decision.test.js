const assert = require('assert');
const fs = require('fs');
const path = require('path');

const workflowPath = path.join(__dirname, '..', 'workflows', 'vouch-check-pr.yml');
const workflow = fs.readFileSync(workflowPath, 'utf8');

const PINNED_VOUCH_SHA = 'd66fa29a64600490892131ad87597c30c91fcac4';

assert.ok(
  workflow.includes(`mitchellh/vouch/action/check-pr@${PINNED_VOUCH_SHA}`),
  `decide() below is a hand transcription of gh-check-pr from vouch/github.nu at ${PINNED_VOUCH_SHA} (v1.5.0). ` +
    'It reads the action, it does not run it, so on its own it agrees with itself whatever the action does. ' +
    'vouch-check-pr.yml now pins a different revision: re-read gh-check-pr there, update decide() and the ' +
    'decision table in .github/AGENTS.md to match it, then set PINNED_VOUCH_SHA to the new SHA.',
);

const actionDefaults = { 'require-vouch': true, 'auto-close': false };

const booleanInput = (name) => {
  const match = workflow.match(new RegExp(`^\\s+${name}:\\s*"?(true|false)"?\\s*$`, 'm'));
  return match ? match[1] === 'true' : actionDefaults[name];
};

const requireVouch = booleanInput('require-vouch');
const autoClose = booleanInput('auto-close');

const commentedStatus = (() => {
  const match = workflow.match(/steps\.vouch\.outputs\.status == '(\w+)'/);
  assert.ok(match, 'the follow-up comment step is not keyed on a vouch status');
  return match[1];
})();

const decide = (author) => {
  if (author === 'bot') return { status: 'skipped', closed: false, actionComments: false };
  if (author === 'collaborator' || author === 'vouched') {
    return { status: 'vouched', closed: false, actionComments: false };
  }
  if (author === 'denounced') {
    if (!autoClose) return { status: 'closed', closed: false, actionComments: false };
    return { status: 'closed', closed: true, actionComments: true };
  }
  if (!requireVouch) return { status: 'allowed', closed: false, actionComments: false };
  if (!autoClose) return { status: 'closed', closed: false, actionComments: false };
  return { status: 'closed', closed: true, actionComments: true };
};

const outcome = (author) => {
  const result = decide(author);
  return { ...result, workflowComments: result.status === commentedStatus };
};

const cases = [
  { author: 'bot', closed: false, comments: 0 },
  { author: 'collaborator', closed: false, comments: 0 },
  { author: 'vouched', closed: false, comments: 0 },
  { author: 'unvouched', closed: false, comments: 1 },
  { author: 'denounced', closed: true, comments: 1 },
];

let failures = 0;
for (const expected of cases) {
  const actual = outcome(expected.author);
  const comments = Number(actual.actionComments) + Number(actual.workflowComments);
  try {
    assert.strictEqual(actual.closed, expected.closed, `${expected.author}: closed`);
    assert.strictEqual(comments, expected.comments, `${expected.author}: comment count`);
    console.log(`ok   ${expected.author} -> ${actual.status}, closed=${actual.closed}, comments=${comments}`);
  } catch (error) {
    failures += 1;
    console.log(`FAIL ${expected.author} -> ${actual.status}, closed=${actual.closed}, comments=${comments}`);
    console.log(`     ${error.message}: expected ${JSON.stringify(expected)}`);
  }
}

console.log(`\nvouch@${PINNED_VOUCH_SHA.slice(0, 7)} require-vouch=${requireVouch} auto-close=${autoClose} comment-on=${commentedStatus}`);

const parseDenounced = (contents) => new Set(contents
  .split('\n')
  .map((line) => line.trim())
  .filter((line) => line.startsWith('-'))
  .map((line) => line.slice(1).split(/\s+/)[0].split(':').pop().toLowerCase())
  .filter(Boolean));

const gate = fs.readFileSync(path.join(__dirname, '..', 'workflows', 'pr-gate.yml'), 'utf8');
assert.ok(
  gate.includes(".filter((line) => line.startsWith('-'))"),
  'pr-gate.yml no longer parses the denounce list the way this test does',
);

const vouched = fs.readFileSync(path.join(__dirname, '..', 'VOUCHED.td'), 'utf8');
const denouncedNow = parseDenounced(vouched);
const sample = parseDenounced([
  '# -notacomment is a comment line',
  '-SpamBot  seeded 2026-08-12',
  '-github:OtherSpammer',
  'realcontributor',
  '',
].join('\n'));

let parseFailures = 0;
for (const [label, actual, expected] of [
  ['denounce entry, with note', sample.has('spambot'), true],
  ['denounce entry, platform prefixed', sample.has('otherspammer'), true],
  ['comment line is not an entry', sample.has('notacomment'), false],
  ['vouched entry is not denounced', sample.has('realcontributor'), false],
  ['live file parses without throwing', denouncedNow instanceof Set, true],
]) {
  try {
    assert.strictEqual(actual, expected, label);
    console.log(`ok   ${label}`);
  } catch (error) {
    parseFailures += 1;
    console.log(`FAIL ${label}: ${error.message}`);
  }
}

console.log(`denounced in VOUCHED.td: ${denouncedNow.size}`);

const total = failures + parseFailures;
console.log(total === 0 ? 'PASS' : `FAIL (${total} assertions)`);
process.exit(total === 0 ? 0 : 1);
