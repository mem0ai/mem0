// Root entry point for the Zapier CLI app.
//
// Zapier's deployed Lambda wrapper hardcodes `require(path.resolve(__dirname, 'index.js'))`
// at the deployment root and ignores package.json "main". Because this is a
// TypeScript app that compiles to dist/, the wrapper would otherwise fail with
// "Cannot find module '/var/task/index.js'" and every auth/action would break.
//
// This shim re-exports the compiled app so the entry point exists where Zapier
// looks for it. Run `npm run build` before `zapier-platform push` so dist/ exists.
module.exports = require('./dist/index.js');
