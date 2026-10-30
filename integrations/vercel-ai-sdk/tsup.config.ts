import { defineConfig } from 'tsup'
import pkg from './package.json'

export default defineConfig([
  {
    dts: true,
    entry: ['src/index.ts'],
    format: ['cjs', 'esm'],
    sourcemap: true,
    // Injected rather than written in the source. A hardcoded literal matches
    // package.json on the day it is written and misreports the client version
    // from the next release bump onwards. Same mechanism as mem0-ts.
    define: {
      __MEM0_PROVIDER_VERSION__: JSON.stringify(pkg.version),
    },
  },
])