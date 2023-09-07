module.exports = {
  '*.{js,ts}': ['eslint --fix', 'eslint'],
  '**/*.ts?(x)': () => 'npm run check-types',
  '*.json': ['prettier --write'],
};
