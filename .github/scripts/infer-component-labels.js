const fs = require('fs');

const COMPONENT_LABELS = [
  'sdk-python',
  'sdk-typescript',
  'vector-store',
  'plugin',
  'rest-api',
  'openmemory',
  'cli',
  'integrations',
  'documentation',
];

function toMatcher(term) {
  const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const prefix = /^[a-z0-9]/i.test(term) ? '\\b' : '';
  return new RegExp(prefix + escaped, 'i');
}

function scoreGroup(text, group) {
  let winner = null;
  let best = 0;
  for (const [label, terms] of Object.entries(group)) {
    const score = terms.reduce((n, term) => n + (toMatcher(term).test(text) ? 1 : 0), 0);
    if (score > best) {
      winner = label;
      best = score;
    }
  }
  return winner;
}

const UMBRELLA = { plugin: 'integrations' };

function inferComponentLabels(text, keywords) {
  if (!text) return [];
  const labels = [scoreGroup(text, keywords.language), scoreGroup(text, keywords.area)].filter(
    Boolean,
  );
  for (const label of labels.slice()) {
    const parent = UMBRELLA[label];
    if (parent && !labels.includes(parent)) labels.push(parent);
  }
  return labels;
}

function loadKeywords(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

module.exports = { COMPONENT_LABELS, inferComponentLabels, loadKeywords };
