/**
 * Branding and ASCII art for mem0 CLI.
 */

import chalk from "chalk";
import ora, { type Ora } from "ora";
import { createRequire } from "node:module";

const _require = createRequire(import.meta.url);
const PKG_VERSION: string = _require("../package.json").version;

export const LOGO = `
███╗   ███╗███████╗███╗   ███╗ ██████╗      ██████╗██╗     ██╗
████╗ ████║██╔════╝████╗ ████║██╔═████╗    ██╔════╝██║     ██║
██╔████╔██║█████╗  ██╔████╔██║██║██╔██║    ██║     ██║     ██║
██║╚██╔╝██║██╔══╝  ██║╚██╔╝██║████╔╝██║    ██║     ██║     ██║
██║ ╚═╝ ██║███████╗██║ ╚═╝ ██║╚██████╔╝    ╚██████╗███████╗██║
╚═╝     ╚═╝╚══════╝╚═╝     ╚═╝ ╚═════╝      ╚═════╝╚══════╝╚═╝
`;

export const LOGO_MINI = "◆ mem0";
export const TAGLINE = "The Memory Layer for AI Agents";

export const BRAND_COLOR = "#8b5cf6";
export const ACCENT_COLOR = "#a78bfa";
export const SUCCESS_COLOR = "#22c55e";
export const ERROR_COLOR = "#ef4444";
export const WARNING_COLOR = "#f59e0b";
export const DIM_COLOR = "#6b7280";

const brand = chalk.hex(BRAND_COLOR);
const accent = chalk.hex(ACCENT_COLOR);
const success = chalk.hex(SUCCESS_COLOR);
const error = chalk.hex(ERROR_COLOR);
const warning = chalk.hex(WARNING_COLOR);
const dim = chalk.hex(DIM_COLOR);

/**
 * Choose a symbol based on TTY/NO_COLOR. Fancy for interactive terminals,
 * plain-text for piped/non-TTY or NO_COLOR environments.
 */
export function sym(fancy: string, plain: string): string {
  if (!process.stdout.isTTY || process.env.NO_COLOR) return plain;
  return fancy;
}

export function printBanner(): void {
  const pad = 3; // horizontal padding each side (matches Rich's padding=(0, 2))
  const logoLines = LOGO.trimEnd().split("\n");
  const tagline = `  ${TAGLINE}`;
  const subtitle = `Node.js SDK · v${PKG_VERSION}`;
  const contentLines = ["", ...logoLines, "", tagline, ""];

  // Compute inner width from longest content line + padding both sides
  const maxContent = Math.max(...contentLines.map((l) => l.length));
  const innerWidth = maxContent + pad * 2;
  const totalWidth = innerWidth + 2; // + 2 for │ borders

  const topBorder = brand(`╭${"─".repeat(totalWidth - 2)}╮`);
  const subtitleFill = totalWidth - 2 - subtitle.length - 3; // 3 = "─ " before subtitle + "─" after
  const bottomBorder = brand(`╰${"─".repeat(subtitleFill)} ${dim(subtitle)} ${"─"}╯`);

  const body = contentLines.map((line) => {
    const rightPad = innerWidth - pad - line.length;
    return `${brand("│")}${" ".repeat(pad)}${brand.bold(line)}${" ".repeat(Math.max(rightPad, 0))}${brand("│")}`;
  });
  // Re-color tagline line with accent instead of brand.bold
  const taglineIdx = body.length - 2; // second-to-last (before trailing empty line)
  const taglineRightPad = innerWidth - pad - tagline.length;
  body[taglineIdx] = `${brand("│")}${" ".repeat(pad)}${accent(tagline)}${" ".repeat(Math.max(taglineRightPad, 0))}${brand("│")}`;

  console.log(topBorder);
  for (const line of body) console.log(line);
  console.log(bottomBorder);
}

export function printSuccess(message: string): void {
  console.log(`${success(sym("✓", "[ok]"))} ${message}`);
}

export function printError(message: string, hint?: string): void {
  console.error(`${error(sym("✗", "[error]") + " Error:")} ${message}`);
  if (hint) {
    console.error(`  ${dim(hint)}`);
  }
}

export function printWarning(message: string): void {
  console.error(`${warning(sym("⚠", "[warn]"))} ${message}`);
}

export function printInfo(message: string): void {
  console.log(`${brand(sym("◆", "*"))} ${message}`);
}

export function printScope(ids: Record<string, string | undefined>): void {
  const parts: string[] = [];
  for (const [key, val] of Object.entries(ids)) {
    if (val) {
      const label = key.replace(/_/g, " ").replace("id", "ID").trim();
      parts.push(`${label}=${val}`);
    }
  }
  if (parts.length > 0) {
    console.log(`  ${dim(`Scope: ${parts.join(", ")}`)}`);
  }
}

export interface TimedStatusContext {
  successMsg: string;
  errorMsg: string;
}

/**
 * Run an async function with a spinner, timing the operation.
 * Equivalent to Python's timed_status context manager.
 */
export async function timedStatus<T>(
  message: string,
  fn: (ctx: TimedStatusContext) => Promise<T>,
): Promise<T> {
  const ctx: TimedStatusContext = { successMsg: "", errorMsg: "" };
  const spinner = ora({ text: dim(message), color: "magenta", stream: process.stderr }).start();
  const start = performance.now();

  try {
    const result = await fn(ctx);
    const elapsed = ((performance.now() - start) / 1000).toFixed(2);
    spinner.stop();
    if (ctx.successMsg) {
      console.error(`${success("✓")} ${ctx.successMsg} (${elapsed}s)`);
    }
    return result;
  } catch (err) {
    const elapsed = ((performance.now() - start) / 1000).toFixed(2);
    spinner.stop();
    if (ctx.errorMsg) {
      console.error(`${error("✗ Error:")} ${ctx.errorMsg} (${elapsed}s)`);
    }
    throw err;
  }
}

/** Format helpers using brand colors for external use. */
export const colors = { brand, accent, success, error, warning, dim };
