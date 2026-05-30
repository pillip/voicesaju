/**
 * Onboarding session store (ISSUE-028).
 *
 * Holds the in-flight 4-step onboarding form state across page navigations
 * (Next.js App Router does not preserve component-local state between page
 * routes). Lifetime = browser session — we intentionally do NOT persist to
 * localStorage because the user's birth date is PII; if they bail mid-flow
 * we want the state to evaporate. Profile creation is handled by ISSUE-029
 * (POST /api/v1/profile), which the /name page submits to.
 *
 * AC mapping:
 * - AC1: setBirthDate persists across navigation to /onboarding/birth-time.
 * - AC2: setBirthTimeUnknown(true) clears hour/minute so the disabled state
 *   on the spinners is meaningful (no stale value).
 * - AC3: back navigation preserves all prior values (default Zustand behaviour;
 *   nothing reads the URL so unmount/remount has no effect).
 *
 * Why Zustand instead of useState + URL state:
 * - State needs to outlive a single page; the Next.js router resets component
 *   trees on route change.
 * - useState + Context would require a layout-level provider; Zustand stores
 *   are framework-agnostic module singletons and trivial to mock in tests.
 * - localStorage / sessionStorage involves PII (birth date) — out of scope
 *   for this issue; ISSUE-029 already encrypts at the API layer.
 */
import { create } from "zustand";

export type CalendarSystem = "solar" | "lunar";
export type Gender = "female" | "male";

export interface OnboardingState {
  // Step 1.
  birthDate: string; // YYYY-MM-DD; '' = not entered yet.
  calendarSystem: CalendarSystem;
  // Step 2.
  birthHour: number | null;
  birthMinute: number | null;
  birthTimeUnknown: boolean;
  // Step 3.
  gender: Gender | null;
  // Step 4.
  name: string; // '' = no name (Screen 5 — name is optional).

  setBirthDate: (v: string) => void;
  setCalendarSystem: (v: CalendarSystem) => void;
  setBirthHour: (v: number | null) => void;
  setBirthMinute: (v: number | null) => void;
  setBirthTimeUnknown: (v: boolean) => void;
  setGender: (v: Gender) => void;
  setName: (v: string) => void;
  reset: () => void;
}

const initialState = {
  birthDate: "",
  calendarSystem: "solar" as CalendarSystem,
  birthHour: null,
  birthMinute: null,
  birthTimeUnknown: false,
  gender: null,
  name: "",
};

export const useOnboardingStore = create<OnboardingState>((set) => ({
  ...initialState,

  setBirthDate: (v) => set({ birthDate: v }),
  setCalendarSystem: (v) => set({ calendarSystem: v }),
  setBirthHour: (v) => set({ birthHour: v }),
  setBirthMinute: (v) => set({ birthMinute: v }),
  /**
   * Toggling "시간 모름" must clear any partially typed hour/minute so the
   * disabled spinner state is unambiguous (otherwise a 14:30 ghost would
   * remain behind a "disabled" overlay — confusing for the user and for
   * the downstream profile API contract).
   */
  setBirthTimeUnknown: (v) =>
    set(
      v
        ? { birthTimeUnknown: true, birthHour: null, birthMinute: null }
        : { birthTimeUnknown: false, birthHour: null, birthMinute: null },
    ),
  setGender: (v) => set({ gender: v }),
  setName: (v) => set({ name: v }),
  reset: () => set(initialState),
}));
