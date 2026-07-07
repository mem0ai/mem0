# Development

## Prerequisites

- Node.js **18+**
- pnpm (`npm install -g pnpm`)

## Setup

From the `node/` directory:

```bash
pnpm install
```

## Running the CLI

There are two ways to run the CLI during development:

### Option 1: Development mode (no build needed)

Uses `tsx` to run TypeScript directly. Pass CLI arguments after `pnpm dev`:

```bash
pnpm dev --help
pnpm dev version
pnpm dev add "test memory" --user-id alice
pnpm dev search "test" --user-id alice
pnpm dev config show
```

> **Note:** Do NOT use `pnpm dev -- --help`. With pnpm, arguments pass through directly — adding `--` inserts a literal `--` that breaks the CLI parser.

### Option 2: Build and run compiled JS

```bash
# Build first
pnpm build

# Run the compiled CLI
node dist/index.js --help
node dist/index.js version
node dist/index.js add "test memory" --user-id alice
```

### Option 3: Link globally (makes `mem0` available system-wide)

```bash
pnpm build
pnpm link --global

# Now use it like a normal CLI
mem0 --help
mem0 version
```

> **Warning:** If you also have the Python CLI installed, both register the `mem0` command. The last one linked/installed wins. Unlink with `pnpm unlink --global`.

## Build

```bash
pnpm build
```

The compiled output is in `dist/`.

## Run tests

```bash
# Run all tests
pnpm test

# Watch mode
pnpm test:watch
```

## Lint

```bash
# Check
pnpm lint

# Auto-fix
pnpm lint:fix
```

## Type checking

```bash
pnpm typecheck
```
