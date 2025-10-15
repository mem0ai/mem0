// @ts-nocheck
import { defineConfig } from 'tsup';

declare const process: any;

export default defineConfig({
  entry: ['src/worker-entry.ts'],
  format: ['esm'],
  target: 'es2020',
  sourcemap: true,
  outDir: 'dist/worker',
  clean: true,
  dts: true,
  platform: 'browser',
  external: [
    // keep heavy native libs external (they will not be used in worker build)
    'sqlite3',
    'pg',
    'redis'
  ],
  esbuildOptions(options) {
    // Ensure Promise, fetch, and other web globals are preserved
    options.define = {
      ...options.define,
      'process.env.NODE_ENV': JSON.stringify(process.env.NODE_ENV || 'production')
    };
  }
});
