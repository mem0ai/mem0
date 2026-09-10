const assert = require('assert');
const fs = require('fs');
const path = require('path');

const gate = fs.readFileSync(path.join(__dirname, '..', 'workflows', 'pr-gate.yml'), 'utf8');

const rootDocsLine = gate.match(/^\s*(const rootDocs = new Set\(\['[\w.-]+'(?:, '[\w.-]+')*\]\);)\s*$/m);
const isDocsLine = gate.match(/^\s*(const isDocs = \(\w+\) => [\w.'"()[\]\/, |&!=><+-]+;)\s*$/m);

assert.ok(
  rootDocsLine,
  'pr-gate.yml no longer declares rootDocs as a single-line Set of quoted filenames. ' +
    'This test evaluates that line to exercise the shipped predicate rather than a copy of it, ' +
    'and only accepts a literal shape, so widen the pattern deliberately or keep the declaration literal.',
);
assert.ok(
  isDocsLine,
  'pr-gate.yml no longer declares isDocs as a single-line arrow expression. ' +
    'This test evaluates that line to exercise the shipped predicate rather than a copy of it, ' +
    'and refuses anything with a statement body, so keep it an expression.',
);

const isDocs = new Function(`${rootDocsLine[1]}\n${isDocsLine[1]}\nreturn isDocs;`)();

const exempt = (files) => files.length > 0 && files.every(isDocs);

const cases = [
  [['docs/a.mdx'], true],
  [['docs/platform/quickstart.mdx'], true],
  [['README.md'], true],
  [['CONTRIBUTING.md'], true],
  [['CODE_OF_CONDUCT.md'], true],
  [['SECURITY.md'], true],
  [['README.md', 'CONTRIBUTING.md', 'docs/x.mdx'], true],
  [['AGENTS.md'], false],
  [['CLAUDE.md'], false],
  [['LLM.md'], false],
  [['README.md', 'AGENTS.md'], false],
  [['README.md', 'mem0/memory/main.py'], false],
  [['skills/mem0/SKILL.md'], false],
  [['.github/AGENTS.md'], false],
  [['.github/workflows/ci.yml'], false],
  [['docs-site/index.md'], false],
  [[], false],
];

let failures = 0;
for (const [files, expected] of cases) {
  const actual = exempt(files);
  const label = files.length ? files.join(', ') : '(no files)';
  if (actual === expected) {
    console.log(`ok   ${label} -> ${actual ? 'exempt' : 'gated'}`);
  } else {
    failures += 1;
    console.log(`FAIL ${label} -> ${actual ? 'exempt' : 'gated'}, expected ${expected ? 'exempt' : 'gated'}`);
  }
}

console.log(failures === 0 ? '\nPASS' : `\nFAIL (${failures} cases)`);
process.exit(failures === 0 ? 0 : 1);
