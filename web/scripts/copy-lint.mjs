#!/usr/bin/env node
/**
 * copy-lint — regex-based deny-list checker for the "누님" voice. ISSUE-097
 * / FR-043 v1.
 *
 * Walks every `.ts`, `.tsx`, `.md` and `.mdx` source file under `web/src`
 * and `web/docs` (if present), pulling out string literals + raw text
 * blocks, and matches each against a small deny-list seeded from
 * `docs/copy_guide.md` §7.2 (DON'T table).
 *
 * v1 scope (intentionally minimal):
 *   1. Formal honorific ending `습니다` in any informal-voice context.
 *   2. Formal honorific ending `입니다` in any informal-voice context.
 *   3. Formal address `고객님` / `회원님` / `여러분` / `당신`.
 *
 * Files are tagged "informal" by default. A file can opt out by including
 * the literal marker `copy-lint: formal-ok` in a comment (used by
 * `/legal/*` pages where 평문체 is allowed per copy_guide §13).
 *
 * Output:
 *   * Each finding prints `path:line:column  RULE  matched-text`.
 *   * Exit code:
 *       0  no findings
 *       1  one or more findings
 *       2  internal error (file read, etc.)
 *
 * Designed to be cheap and easy to extend — append a new rule to
 * `RULES` and the suite picks it up. Future revisions can grow this
 * into a tokenised lint, but v1 trades precision for legibility.
 *
 * Architecture refs:
 *   docs/copy_guide.md §7.2 DON'T table
 *   ISSUE-097 Implementation Notes
 */

import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const SCRIPT_DIR = resolve(__filename, '..');
const WEB_ROOT = resolve(SCRIPT_DIR, '..');

/**
 * Deny-list. Each rule has:
 *   id          — short stable code printed in the report.
 *   pattern     — RegExp; `g` flag so we can find every occurrence.
 *   description — human-readable rationale (printed next to the match).
 *
 * The regex bodies are intentionally simple — fancy lookbehind/look
 * ahead invites engine surprises and slows v1 adoption.
 */
const RULES = [
  {
    id: 'NO-FORMAL-SEUMNIDA',
    // 습니다 / 십니다 — formal honorific ending. Disallowed in informal
    // voice contexts (all of /reading, /tarot, /me, /auth surfaces).
    pattern: /습니다|십니다/g,
    description: '평문체 종결어 — 누님 voice는 반말. (-습니다 / -십니다 금지)',
  },
  {
    id: 'NO-FORMAL-IPNIDA',
    pattern: /입니다/g,
    description: '평문체 종결어 — 누님 voice는 반말. (-입니다 금지)',
  },
  {
    id: 'NO-FORMAL-ADDRESS',
    // 고객님 / 회원님 / 당신 / 여러분 — formal address terms.
    pattern: /고객님|회원님|여러분|당신/g,
    description: '정중어 호칭 금지 — copy_guide §7.2',
  },
];

/**
 * Files matching this set are scanned. Other extensions are silently
 * skipped (we never lint .json, .css, etc.).
 */
const SCAN_EXTENSIONS = new Set(['.ts', '.tsx', '.md', '.mdx']);

/**
 * Roots scanned by default. Resolved relative to `web/`.
 *
 * `src` covers all runtime copy; the linter is intentionally aggressive
 * here. Excludes test files (see SKIP_DIR_NAMES) so the lint suite can
 * intentionally seed a violation fixture.
 */
const SCAN_ROOTS = ['src'];

/**
 * Skipped on the way down the tree. `__tests__` houses fixtures that
 * intentionally include violations (so the linter itself can be
 * unit-tested). `node_modules` is the obvious one.
 *
 * `legal`, `error`, `preview` are surfaces where 평문체 is the intended
 * voice (legal copy, system error screens, design previews). Per
 * `docs/copy_guide.md` §13 these are exempt from the 누님 voice. We
 * exempt them at the directory level rather than per-file because the
 * exemption is structural — every page under those roots is allowed
 * to use formal tone.
 */
const SKIP_DIR_NAMES = new Set([
  'node_modules',
  '__tests__',
  '.next',
  'dist',
  'build',
  'legal',
  'error',
  'preview',
]);

/**
 * Marker that lets a file opt out of the deny-list. Used by
 * `/legal/*` pages where 평문체 is the intended voice.
 */
const FORMAL_OK_MARKER = 'copy-lint: formal-ok';

/**
 * Walks a directory tree synchronously and yields file paths matching
 * SCAN_EXTENSIONS. Uses an explicit stack so we don't blow the call
 * stack on deep monorepos.
 */
function* walk(root) {
  if (!existsSync(root)) return;
  const stack = [root];
  while (stack.length > 0) {
    const dir = stack.pop();
    let entries;
    try {
      entries = readdirSync(dir, { withFileTypes: true });
    } catch (err) {
      // Unreadable directory — skip silently. The lint is best-effort.
      continue;
    }
    for (const entry of entries) {
      const full = join(dir, entry.name);
      if (entry.isDirectory()) {
        if (SKIP_DIR_NAMES.has(entry.name)) continue;
        stack.push(full);
        continue;
      }
      const dot = entry.name.lastIndexOf('.');
      if (dot < 0) continue;
      const ext = entry.name.slice(dot);
      if (!SCAN_EXTENSIONS.has(ext)) continue;
      yield full;
    }
  }
}

/**
 * Returns the 1-based line and 1-based column for a flat character
 * offset within `text`. Used for reporting.
 */
function locate(text, offset) {
  let line = 1;
  let col = 1;
  for (let i = 0; i < offset && i < text.length; i += 1) {
    if (text[i] === '\n') {
      line += 1;
      col = 1;
    } else {
      col += 1;
    }
  }
  return { line, col };
}

/**
 * Returns true if the line at `lineNumber` (1-based) inside `source`
 * looks like a code comment. We skip comment lines because JSDoc /
 * inline rationale frequently uses formal Korean to explain what a
 * component does — that is not user-facing copy and the linter would
 * generate too much noise to be useful.
 *
 * Heuristic only: matches lines whose first non-whitespace characters
 * are `//`, `/*`, `*`, or `* /` (JSDoc continuation). This catches the
 * vast majority of comment lines in TS/TSX/MDX without a real parser.
 */
function isCommentLine(source, lineNumber) {
  const lines = source.split('\n');
  const line = lines[lineNumber - 1] ?? '';
  const trimmed = line.replace(/^[\s\t]+/, '');
  if (trimmed.startsWith('//')) return true;
  if (trimmed.startsWith('/*')) return true;
  if (trimmed.startsWith('*')) return true;
  return false;
}

/**
 * Scans one file. Returns a list of findings. Each finding:
 *   { file, line, col, ruleId, description, match }
 */
export function scanFile(absolutePath, displayPath, source) {
  // formal-ok opt-out: skip the entire file.
  if (source.includes(FORMAL_OK_MARKER)) return [];

  const findings = [];
  for (const rule of RULES) {
    // Clone the regex per pass — global regexes carry `.lastIndex`
    // state, which would leak between rules if we reused them.
    const re = new RegExp(rule.pattern.source, rule.pattern.flags);
    let match;
    while ((match = re.exec(source)) !== null) {
      const { line, col } = locate(source, match.index);
      // Skip matches inside comment lines — JSDoc rationale frequently
      // contains formal Korean ("표시됩니다", "사용됩니다") that is not
      // user-facing copy.
      if (isCommentLine(source, line)) continue;
      findings.push({
        file: displayPath,
        line,
        col,
        ruleId: rule.id,
        description: rule.description,
        match: match[0],
      });
    }
  }
  return findings;
}

function formatFinding(f) {
  return `${f.file}:${f.line}:${f.col}  [${f.ruleId}]  "${f.match}" — ${f.description}`;
}

/**
 * Main entry point. Resolves the scan roots relative to `web/`,
 * iterates files, and prints findings. CI calls this directly.
 */
function main() {
  const findings = [];

  for (const root of SCAN_ROOTS) {
    const abs = resolve(WEB_ROOT, root);
    for (const file of walk(abs)) {
      let source;
      try {
        source = readFileSync(file, 'utf8');
      } catch (err) {
        process.stderr.write(`copy-lint: failed to read ${file}: ${err.message}\n`);
        process.exit(2);
      }
      const display = relative(WEB_ROOT, file);
      const fileFindings = scanFile(file, display, source);
      for (const f of fileFindings) findings.push(f);
    }
  }

  if (findings.length === 0) {
    process.stdout.write('copy-lint: 0 violations — 누님 톤 통일 OK ✦\n');
    process.exit(0);
  }

  process.stdout.write(`copy-lint: ${findings.length} violation(s) found\n\n`);
  for (const f of findings) {
    process.stdout.write(`  ${formatFinding(f)}\n`);
  }
  process.stdout.write(
    '\nTo opt a file out (e.g. /legal/*), add the comment marker:\n  // copy-lint: formal-ok\n',
  );
  process.exit(1);
}

// Allow `node copy-lint.mjs` direct invocation; export `scanFile` for
// the vitest suite to test the lint logic without spawning a subprocess.
if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}
