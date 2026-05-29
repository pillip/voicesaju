import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { BottomTabBar } from "@/components/nav/BottomTabBar";

describe("BottomTabBar", () => {
  it("renders the three default tabs (사주 / 오늘의 타로 / 마이)", () => {
    render(<BottomTabBar active="saju" />);
    expect(
      screen.getByRole("navigation", { name: "주요 메뉴" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /사주/ })).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /오늘의 타로/ }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /마이/ })).toBeInTheDocument();
  });

  it('marks the active tab with aria-current="page"', () => {
    render(<BottomTabBar active="tarot" />);
    const tarot = screen.getByRole("link", { name: /오늘의 타로/ });
    expect(tarot).toHaveAttribute("aria-current", "page");
    const saju = screen.getByRole("link", { name: /사주/ });
    expect(saju).not.toHaveAttribute("aria-current");
  });

  it("returns null DOM-empty when hideOnPlayback={true}", () => {
    const { container } = render(<BottomTabBar hideOnPlayback />);
    expect(container).toBeEmptyDOMElement();
  });

  it("passes axe-core scan with zero AA violations", async () => {
    const { container } = render(<BottomTabBar active="me" />);
    const results = await axe(container);
    expect(results.violations).toEqual([]);
  });
});
