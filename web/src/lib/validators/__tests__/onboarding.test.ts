/**
 * Unit tests for onboarding per-step validators (ISSUE-028).
 *
 * Each AC validation rule from issues.md maps to a test below. The validators
 * live in `src/lib/validators/onboarding.ts` so they can be exercised by both
 * the per-step pages (Vitest) and a future Playwright spec without React.
 */
import { describe, expect, it } from "vitest";
import {
  validateBirthDate,
  validateName,
  validateBirthTime,
  type BirthDateError,
  type NameError,
} from "@/lib/validators/onboarding";

describe("validateBirthDate (ISSUE-028 AC1, ux_spec Screen 2 error states)", () => {
  it("accepts a valid YYYY-MM-DD solar date in the past", () => {
    expect(validateBirthDate("1997-03-15", "2026-05-29")).toBeNull();
  });

  it("rejects a malformed date string", () => {
    expect(validateBirthDate("1997/3/15", "2026-05-29")).toBe<BirthDateError>(
      "format",
    );
  });

  it("rejects an empty string as a format error", () => {
    expect(validateBirthDate("", "2026-05-29")).toBe<BirthDateError>("format");
  });

  it("rejects a date that does not exist (Feb 30)", () => {
    expect(validateBirthDate("1997-02-30", "2026-05-29")).toBe<BirthDateError>(
      "invalid",
    );
  });

  it('rejects a future date (per AC: "no future dates")', () => {
    expect(validateBirthDate("2099-01-01", "2026-05-29")).toBe<BirthDateError>(
      "future",
    );
  });

  it("rejects dates before 1900 (copy_guide §2 error)", () => {
    expect(validateBirthDate("1850-06-01", "2026-05-29")).toBe<BirthDateError>(
      "too-old",
    );
  });

  it("accepts today as a valid date (boundary)", () => {
    expect(validateBirthDate("2026-05-29", "2026-05-29")).toBeNull();
  });
});

describe("validateBirthTime (ISSUE-028 AC2 — spinners constrain values)", () => {
  it("accepts the empty/known-zero pair when 모름 is checked", () => {
    expect(
      validateBirthTime({ hour: null, minute: null, unknown: true }),
    ).toBeNull();
  });

  it("accepts valid hour + minute pair", () => {
    expect(
      validateBirthTime({ hour: 14, minute: 30, unknown: false }),
    ).toBeNull();
  });

  it("rejects hour out of range", () => {
    expect(validateBirthTime({ hour: 25, minute: 0, unknown: false })).toBe(
      "hour-range",
    );
  });

  it("rejects minute out of range", () => {
    expect(validateBirthTime({ hour: 12, minute: 60, unknown: false })).toBe(
      "minute-range",
    );
  });

  it("rejects partial hour-only entry when 모름 is unchecked (CTA must be disabled)", () => {
    expect(validateBirthTime({ hour: 12, minute: null, unknown: false })).toBe(
      "incomplete",
    );
  });

  it("rejects partial minute-only entry when 모름 is unchecked", () => {
    expect(validateBirthTime({ hour: null, minute: 30, unknown: false })).toBe(
      "incomplete",
    );
  });

  it("rejects fully empty entry when 모름 is unchecked (empty state)", () => {
    expect(
      validateBirthTime({ hour: null, minute: null, unknown: false }),
    ).toBe("incomplete");
  });
});

describe('validateName (ISSUE-028 AC4 — "이름은 10자 이내")', () => {
  it("accepts a name with exactly 10 chars (boundary)", () => {
    expect(validateName("가나다라마바사아자차")).toBeNull();
  });

  it("accepts a 1-char name", () => {
    expect(validateName("효")).toBeNull();
  });

  it("accepts an empty name (Screen 5 — name is optional)", () => {
    expect(validateName("")).toBeNull();
  });

  it('rejects a name > 10 chars with the "too-long" error', () => {
    expect(validateName("가나다라마바사아자차카")).toBe<NameError>("too-long");
  });

  it("rejects whitespace-only as too-long? — actually whitespace-only treated as empty (allowed)", () => {
    expect(validateName("   ")).toBeNull();
  });
});
