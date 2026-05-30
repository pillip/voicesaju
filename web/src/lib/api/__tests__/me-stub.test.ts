import { describe, expect, it } from "vitest";
import { buildMeStub } from "@/lib/api/me-stub";

describe("buildMeStub — entitlement stub (ISSUE-030)", () => {
  it("returns the non-member default when no override is supplied", () => {
    expect(buildMeStub()).toEqual({
      entitlement_kind: "none",
      signup_grant_remaining: 0,
      monthly_remaining: 0,
    });
  });

  it("returns the non-member default when override is null", () => {
    expect(buildMeStub(null).entitlement_kind).toBe("none");
  });

  it("returns the non-member default when override is an unknown string", () => {
    expect(buildMeStub("garbage").entitlement_kind).toBe("none");
  });

  it('flips signup_grant_remaining to 1 when override === "free_token"', () => {
    const res = buildMeStub("free_token");
    expect(res.entitlement_kind).toBe("free_token");
    expect(res.signup_grant_remaining).toBe(1);
    expect(res.monthly_remaining).toBe(0);
  });

  it('returns the payment-required shape when override === "payment"', () => {
    const res = buildMeStub("payment");
    expect(res.entitlement_kind).toBe("payment");
    expect(res.signup_grant_remaining).toBe(0);
    expect(res.monthly_remaining).toBe(0);
  });

  it('returns subscriber state with monthly_remaining=1 when override === "subscription"', () => {
    const res = buildMeStub("subscription");
    expect(res.entitlement_kind).toBe("subscription");
    expect(res.monthly_remaining).toBe(1);
  });
});
