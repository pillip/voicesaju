/**
 * Unit tests for the onboarding Zustand store (ISSUE-028).
 *
 * The store holds the 4-step form state across page navigations (session-only,
 * not persisted) so back navigation preserves prior answers (AC3).
 */
import { describe, expect, it, beforeEach } from "vitest";
import { useOnboardingStore } from "@/lib/stores/onboarding-store";

describe("useOnboardingStore", () => {
  beforeEach(() => {
    // Reset between tests — Zustand stores are module-singletons.
    useOnboardingStore.getState().reset();
  });

  it("starts with all fields at their initial empty/default values", () => {
    const s = useOnboardingStore.getState();
    expect(s.birthDate).toBe("");
    expect(s.calendarSystem).toBe("solar");
    expect(s.birthHour).toBeNull();
    expect(s.birthMinute).toBeNull();
    expect(s.birthTimeUnknown).toBe(false);
    expect(s.gender).toBeNull();
    expect(s.name).toBe("");
  });

  it("setBirthDate persists the value for later reads (AC1, AC3)", () => {
    useOnboardingStore.getState().setBirthDate("1997-03-15");
    expect(useOnboardingStore.getState().birthDate).toBe("1997-03-15");
  });

  it("setCalendarSystem flips solar ↔ lunar", () => {
    useOnboardingStore.getState().setCalendarSystem("lunar");
    expect(useOnboardingStore.getState().calendarSystem).toBe("lunar");
    useOnboardingStore.getState().setCalendarSystem("solar");
    expect(useOnboardingStore.getState().calendarSystem).toBe("solar");
  });

  it("setBirthTimeUnknown(true) clears hour/minute (AC2 — disables spinners)", () => {
    const s = useOnboardingStore.getState();
    s.setBirthHour(14);
    s.setBirthMinute(30);
    s.setBirthTimeUnknown(true);
    const after = useOnboardingStore.getState();
    expect(after.birthTimeUnknown).toBe(true);
    expect(after.birthHour).toBeNull();
    expect(after.birthMinute).toBeNull();
  });

  it("setBirthTimeUnknown(false) leaves cleared values null (user re-enters)", () => {
    const s = useOnboardingStore.getState();
    s.setBirthTimeUnknown(true);
    s.setBirthTimeUnknown(false);
    const after = useOnboardingStore.getState();
    expect(after.birthTimeUnknown).toBe(false);
    expect(after.birthHour).toBeNull();
    expect(after.birthMinute).toBeNull();
  });

  it("setGender persists 여 or 남 (matches profile API enum)", () => {
    useOnboardingStore.getState().setGender("female");
    expect(useOnboardingStore.getState().gender).toBe("female");
    useOnboardingStore.getState().setGender("male");
    expect(useOnboardingStore.getState().gender).toBe("male");
  });

  it("setName persists the name (≤ 10 chars enforced at the field level)", () => {
    useOnboardingStore.getState().setName("효주");
    expect(useOnboardingStore.getState().name).toBe("효주");
  });

  it("reset() returns the store to initial values", () => {
    const s = useOnboardingStore.getState();
    s.setBirthDate("1997-03-15");
    s.setGender("female");
    s.setName("효주");
    s.reset();
    const after = useOnboardingStore.getState();
    expect(after.birthDate).toBe("");
    expect(after.gender).toBeNull();
    expect(after.name).toBe("");
  });

  it("back-navigation contract: setting a value then navigating away does NOT reset it (AC3)", () => {
    const s = useOnboardingStore.getState();
    s.setBirthDate("1997-03-15");
    // Simulate a navigation by reading state without any mutation.
    const after = useOnboardingStore.getState();
    expect(after.birthDate).toBe("1997-03-15");
  });
});
