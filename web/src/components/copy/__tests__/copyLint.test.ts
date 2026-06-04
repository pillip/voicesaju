/**
 * ISSUE-097 — `copy-lint` scanner unit tests (AC6).
 *
 * Imports the exported `scanFile` from `web/scripts/copy-lint.mjs` and
 * runs it against synthetic source strings. We exercise the scanner
 * here (not the CLI) because:
 *
 *   1. The CLI walks `web/src/` against the real codebase — that's the
 *      `pnpm copy:lint` smoke. Unit tests should not depend on the
 *      mutable repo state.
 *   2. The deny-list rules are the contract; the walker is plumbing.
 *
 * Lives under `__tests__/` (not in `scripts/`) so the existing vitest
 * include glob (`src/**\/*.test.{ts,tsx}`) picks it up without config
 * churn.
 */

import { describe, expect, it } from 'vitest';

// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-expect-error — `.mjs` import from a `.ts` test is supported by vitest at runtime.
import { scanFile } from '../../../../scripts/copy-lint.mjs';

const FAKE_PATH = '/abs/path/fake.tsx';
const DISPLAY = 'src/fake.tsx';

describe('copy-lint scanFile — AC6 (deny-list rules)', () => {
  it('flags formal honorific 습니다 in user-facing strings', () => {
    const src = "const COPY = '결제가 완료되었습니다';\n";
    const findings = scanFile(FAKE_PATH, DISPLAY, src);
    expect(findings.length).toBeGreaterThanOrEqual(1);
    expect(findings[0].ruleId).toBe('NO-FORMAL-SEUMNIDA');
    expect(findings[0].match).toBe('습니다');
  });

  it('flags 입니다', () => {
    const src = "const COPY = '이것이 너의 사주입니다';\n";
    const findings = scanFile(FAKE_PATH, DISPLAY, src);
    expect(findings.some((f: { ruleId: string }) => f.ruleId === 'NO-FORMAL-IPNIDA')).toBe(true);
  });

  it('flags formal address terms 고객님 / 회원님 / 여러분 / 당신', () => {
    const src = [
      "const A = '고객님 안녕하세요';",
      "const B = '회원님께';",
      "const C = '여러분';",
      "const D = '당신의 운명';",
      '',
    ].join('\n');
    const findings = scanFile(FAKE_PATH, DISPLAY, src);
    const matches = findings.map((f: { match: string }) => f.match).sort();
    expect(matches).toEqual(expect.arrayContaining(['고객님', '회원님', '여러분', '당신']));
    expect(findings.every((f: { ruleId: string }) => f.ruleId === 'NO-FORMAL-ADDRESS')).toBe(true);
  });

  it('reports line and column 1-based', () => {
    const src = [
      '// header',
      "const COPY = '음, 그러게';",
      "const FORMAL = '완료되었습니다';",
    ].join('\n');
    const findings = scanFile(FAKE_PATH, DISPLAY, src);
    expect(findings).toHaveLength(1);
    expect(findings[0].line).toBe(3);
    expect(findings[0].col).toBeGreaterThanOrEqual(1);
  });

  it('honours the `copy-lint: formal-ok` opt-out marker (whole file skipped)', () => {
    const src = ['// copy-lint: formal-ok', "const COPY = '결제가 완료되었습니다';"].join('\n');
    const findings = scanFile(FAKE_PATH, DISPLAY, src);
    expect(findings).toHaveLength(0);
  });

  it('skips matches inside comment lines (JSDoc / block / single-line)', () => {
    const src = [
      '/**',
      ' * 이 컴포넌트는 결제가 완료되었습니다 화면입니다.',
      ' */',
      "const COPY = '음, 그러게';",
    ].join('\n');
    const findings = scanFile(FAKE_PATH, DISPLAY, src);
    expect(findings).toHaveLength(0);
  });

  it('still flags violations even when adjacent lines are comments', () => {
    const src = [
      '// 이건 무시: 입니다',
      "const COPY = '결제가 완료되었습니다';",
      '// 다음 줄도 무시: 고객님',
    ].join('\n');
    const findings = scanFile(FAKE_PATH, DISPLAY, src);
    // Only line 2 violates; comments are stripped.
    expect(findings).toHaveLength(1);
    expect(findings[0].line).toBe(2);
  });

  it('returns an empty list for clean 누님-tone copy', () => {
    const src = [
      "const A = '음, 그러게.';",
      "const B = '받아쳐. 너 잘못 아니야.';",
      "const C = '다시 들려줄게.';",
    ].join('\n');
    const findings = scanFile(FAKE_PATH, DISPLAY, src);
    expect(findings).toHaveLength(0);
  });
});

describe('copy-lint scanFile — rule shape', () => {
  it('each finding includes file, line, col, ruleId, description, match', () => {
    const src = "const COPY = '완료되었습니다';\n";
    const findings = scanFile(FAKE_PATH, DISPLAY, src);
    expect(findings[0]).toMatchObject({
      file: DISPLAY,
      line: expect.any(Number),
      col: expect.any(Number),
      ruleId: expect.any(String),
      description: expect.any(String),
      match: expect.any(String),
    });
  });
});
