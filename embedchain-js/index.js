const { EmbedChainApp } = require("./embedchain/embedchain");

async function App() {
  const app = new EmbedChainApp();
  await app.init_app;
  return app;
}

module.exports = { App };
