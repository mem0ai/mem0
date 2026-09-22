// Zapier's Lambda wrapper requires `<root>/index.js` and ignores package.json
// "main", so re-export the compiled app from the root. Run `npm run build` first.
module.exports = require('./dist/index.js');
