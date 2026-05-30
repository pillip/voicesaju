/**
 * Per-step input validators for the onboarding flow (ISSUE-028).
 *
 * Kept React-free so the same rules can be exercised by Vitest unit tests,
 * the per-page React event handlers, and a future Playwright spec without
 * pulling in the rendering layer. Error codes map 1:1 to the copy_guide §2/§3
 * Korean strings — the consumer chooses how/where to surface them.
 */

/** Possible birth-date validation outcomes. `null` = valid. */
export type BirthDateError = "format" | "invalid" | "future" | "too-old";

export type NameError = "too-long";

export type BirthTimeError = "hour-range" | "minute-range" | "incomplete";

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Validate a YYYY-MM-DD birth date. Pass `today` as a YYYY-MM-DD string for
 * deterministic testing — the page passes `new Date().toISOString().slice(0,10)`.
 *
 * - format: doesn't match YYYY-MM-DD.
 * - invalid: date components don't form a real calendar date (Feb 30).
 * - future: parsed date is strictly after today.
 * - too-old: parsed date is before 1900-01-01.
 */
export function validateBirthDate(
  value: string,
  today: string,
): BirthDateError | null {
  if (!DATE_RE.test(value)) return "format";
  const [yStr, mStr, dStr] = value.split("-");
  const y = Number(yStr);
  const m = Number(mStr);
  const d = Number(dStr);
  // Construct as UTC midnight so timezone doesn't bump the day.
  const parsed = new Date(Date.UTC(y, m - 1, d));
  if (
    parsed.getUTCFullYear() !== y ||
    parsed.getUTCMonth() !== m - 1 ||
    parsed.getUTCDate() !== d
  ) {
    return "invalid";
  }
  if (y < 1900) return "too-old";
  // Compare YYYY-MM-DD strings directly — this avoids local-timezone DST
  // surprises when comparing two Date objects.
  if (value > today) return "future";
  return null;
}

/**
 * Korean inline error copy keyed by the BirthDateError code. Centralised so
 * the page renders the same string the copy guide prescribes and the test
 * suite can assert against a single source of truth.
 */
export function birthDateErrorCopy(code: BirthDateError): string {
  switch (code) {
    case "format":
      return "그 형식이 아니야. YYYY-MM-DD로 적어줘.";
    case "invalid":
      return "그 날짜는 존재하지 않아.";
    case "future":
      return "아직 태어나지 않았네.";
    case "too-old":
      return "너무 옛날인데. 다시 봐줘.";
  }
}

export interface BirthTimeFields {
  hour: number | null;
  minute: number | null;
  unknown: boolean;
}

/**
 * Validate the birth time fields. Returns null when the form is in a valid
 * submittable state — either both hour+minute are present in range, or the
 * "시간 모름" checkbox is checked.
 */
export function validateBirthTime(
  fields: BirthTimeFields,
): BirthTimeError | null {
  if (fields.unknown) return null;
  const { hour, minute } = fields;
  if (hour === null || minute === null) return "incomplete";
  if (hour < 0 || hour > 23) return "hour-range";
  if (minute < 0 || minute > 59) return "minute-range";
  return null;
}

/**
 * Validate the name field. Names are optional — empty is valid (Screen 5).
 * AC4 caps at 10 characters; copy_guide §3.5b actually says 20 but the issue
 * AC explicitly overrides that ("이름은 10자 이내로 적어줘"), so AC wins.
 *
 * Whitespace-only input is collapsed to empty (allowed) because the user
 * almost certainly meant "skip".
 */
export function validateName(value: string): NameError | null {
  const trimmed = value.trim();
  if (trimmed.length === 0) return null;
  if (trimmed.length > 10) return "too-long";
  return null;
}

export const NAME_TOO_LONG_COPY = "이름은 10자 이내로 적어줘";
