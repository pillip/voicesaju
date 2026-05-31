/**
 * Lookup tables for 천간 / 지지 / 오행 / 십신 used by `<SajuFullChart>` and
 * `/me/saju` (ISSUE-064).
 *
 * The backend `saju.engine` emits chart pillars with the raw stem/branch
 * characters (e.g. "갑", "자") and an `element` ("목"/"화"/...) and an
 * optional `ten_god` ("비견", "정관", ...). The frontend mostly just
 * displays these strings as-is — the only embedded data here is the
 * 천간-to-오행 mapping used by the screen-reader announcement format
 * ("년주 천간 무자, 오행 수, 십신 비견") when the backend payload happens
 * to omit a derived field.
 */

/** All ten 천간 in their conventional order (갑 ~ 계). */
export const HEAVENLY_STEMS = [
  "갑",
  "을",
  "병",
  "정",
  "무",
  "기",
  "경",
  "신",
  "임",
  "계",
] as const;

/** All twelve 지지 in their conventional order (자 ~ 해). */
export const EARTHLY_BRANCHES = [
  "자",
  "축",
  "인",
  "묘",
  "진",
  "사",
  "오",
  "미",
  "신",
  "유",
  "술",
  "해",
] as const;

export type HeavenlyStem = (typeof HEAVENLY_STEMS)[number];
export type EarthlyBranch = (typeof EARTHLY_BRANCHES)[number];
export type WuXing = "목" | "화" | "토" | "금" | "수";

/**
 * 천간 → 오행 mapping (the canonical "갑/을 → 木, 병/정 → 火, ..." table).
 * Used as a fallback when the backend hasn't pre-computed an `element`.
 */
export const STEM_TO_ELEMENT: Record<HeavenlyStem, WuXing> = {
  갑: "목",
  을: "목",
  병: "화",
  정: "화",
  무: "토",
  기: "토",
  경: "금",
  신: "금",
  임: "수",
  계: "수",
};

/**
 * Human-friendly description of each 오행 (used by tooltip content).
 * Kept short — copy_guide §7 voice is terse "큰 누님".
 */
export const ELEMENT_DESCRIPTIONS: Record<WuXing, string> = {
  목: "나무 — 성장과 곧음",
  화: "불 — 열정과 표현",
  토: "흙 — 중심과 안정",
  금: "쇠 — 결단과 절제",
  수: "물 — 흐름과 지혜",
};

/**
 * Pillar-key → 한국어 column label used by the table header.
 * 시 = Hour, 일 = Day, 월 = Month, 년 = Year.
 */
export const PILLAR_LABELS = {
  year: "년",
  month: "월",
  day: "일",
  hour: "시",
} as const;

/**
 * Pillar-key → 한국어 "년주" / "월주" / "일주" / "시주" label used by
 * the screen-reader announcement format (AC5 of ISSUE-064).
 */
export const PILLAR_FULL_LABELS = {
  year: "년주",
  month: "월주",
  day: "일주",
  hour: "시주",
} as const;

export type PillarKey = keyof typeof PILLAR_LABELS;
