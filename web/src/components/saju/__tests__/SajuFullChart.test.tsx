/**
 * Unit tests for `<SajuFullChart>` (ISSUE-064, Screen 17).
 *
 * AC coverage:
 *   AC1 — 4 pillars render with KR character labels.
 *   AC2 — birth_time_known=false → Hour Pillar shows "모름", de-emphasized.
 *   AC3 — Tap any cell → tooltip with 오행 + 십신.
 *   AC4 — Arrow-key navigation moves focus across the grid.
 *   AC5 — Each cell exposes a screen-reader aria-label of the form
 *         "년주 천간 무자, 오행 수, 십신 비견".
 */
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { SajuFullChart } from "@/components/saju/SajuFullChart";
import type { SajuChartPayload } from "@/lib/api/profile";

const KNOWN_CHART: SajuChartPayload = {
  year: { stem: "무", branch: "자", element: "수", ten_god: "편재" },
  month: { stem: "갑", branch: "오", element: "화", ten_god: "정관" },
  day: { stem: "경", branch: "신", element: "금", ten_god: "비견" },
  hour: { stem: "정", branch: "묘", element: "목", ten_god: "정인" },
  engine_version: "saju.v1.0",
};

const UNKNOWN_HOUR_CHART: SajuChartPayload = {
  ...KNOWN_CHART,
  hour: null,
};

describe("<SajuFullChart /> (ISSUE-064)", () => {
  it("AC1: renders 4 pillars with KR character labels in the column headers", () => {
    render(<SajuFullChart chart={KNOWN_CHART} birthTimeKnown={true} />);
    expect(screen.getByTestId("saju-full-chart-col-year").textContent).toBe(
      "년",
    );
    expect(screen.getByTestId("saju-full-chart-col-month").textContent).toBe(
      "월",
    );
    expect(screen.getByTestId("saju-full-chart-col-day").textContent).toBe(
      "일",
    );
    expect(screen.getByTestId("saju-full-chart-col-hour").textContent).toBe(
      "시",
    );
  });

  it("AC1: renders 천간 / 지지 / 오행 / 십신 row labels", () => {
    render(<SajuFullChart chart={KNOWN_CHART} birthTimeKnown={true} />);
    expect(screen.getByTestId("saju-full-chart-row-천간")).toBeInTheDocument();
    expect(screen.getByTestId("saju-full-chart-row-지지")).toBeInTheDocument();
    expect(screen.getByTestId("saju-full-chart-row-오행")).toBeInTheDocument();
    expect(screen.getByTestId("saju-full-chart-row-십신")).toBeInTheDocument();
  });

  it("AC1: 년주 cells render heaven/earth/element/ten-god characters", () => {
    render(<SajuFullChart chart={KNOWN_CHART} birthTimeKnown={true} />);
    // The 천간 row of the 년 column should show "무" (heaven stem of 년주).
    expect(screen.getByTestId("saju-full-cell-천간-year").textContent).toBe(
      "무",
    );
    expect(screen.getByTestId("saju-full-cell-지지-year").textContent).toBe(
      "자",
    );
    expect(screen.getByTestId("saju-full-cell-오행-year").textContent).toBe(
      "수",
    );
    expect(screen.getByTestId("saju-full-cell-십신-year").textContent).toBe(
      "편재",
    );
  });

  it('AC2: birth_time_known=false → Hour Pillar shows "모름" + footer hint', () => {
    render(<SajuFullChart chart={UNKNOWN_HOUR_CHART} birthTimeKnown={false} />);
    // Every 시 column cell renders "모름".
    expect(screen.getByTestId("saju-full-cell-천간-hour").textContent).toBe(
      "모름",
    );
    expect(screen.getByTestId("saju-full-cell-지지-hour").textContent).toBe(
      "모름",
    );
    expect(screen.getByTestId("saju-full-cell-오행-hour").textContent).toBe(
      "모름",
    );
    expect(screen.getByTestId("saju-full-cell-십신-hour").textContent).toBe(
      "모름",
    );
    // The de-emphasized italic styling carries the "italic" tailwind utility.
    const heavenHour = screen.getByTestId("saju-full-cell-천간-hour");
    expect(heavenHour.className).toMatch(/italic/);
    // Footer hint is rendered.
    expect(
      screen.getByTestId("saju-full-chart-hour-unknown"),
    ).toBeInTheDocument();
  });

  it("AC3: tapping a cell opens a tooltip with 오행 + 십신", () => {
    render(<SajuFullChart chart={KNOWN_CHART} birthTimeKnown={true} />);
    const dayCell = screen.getByTestId("saju-full-cell-천간-day");
    fireEvent.click(dayCell);
    const tooltip = screen.getByTestId("saju-full-tooltip-day");
    expect(tooltip).toBeInTheDocument();
    expect(tooltip.textContent).toMatch(/오행\s*—\s*금/);
    expect(tooltip.textContent).toMatch(/십신\s*—\s*비견/);
    // aria-describedby wires cell ↔ tooltip for screen readers (NFR-013).
    expect(dayCell.getAttribute("aria-describedby")).toBe(
      tooltip.getAttribute("id"),
    );
  });

  it("AC3: tapping the same cell again closes the tooltip", () => {
    render(<SajuFullChart chart={KNOWN_CHART} birthTimeKnown={true} />);
    const cell = screen.getByTestId("saju-full-cell-천간-month");
    fireEvent.click(cell);
    expect(screen.queryByTestId("saju-full-tooltip-month")).toBeInTheDocument();
    fireEvent.click(cell);
    expect(
      screen.queryByTestId("saju-full-tooltip-month"),
    ).not.toBeInTheDocument();
  });

  it("AC4: ArrowRight from 일주 천간 moves focus to 시주 천간", () => {
    render(<SajuFullChart chart={KNOWN_CHART} birthTimeKnown={true} />);
    const dayHeavenCell = screen.getByTestId("saju-full-cell-천간-day");
    // Initial focus lands on 일주 천간 (tabIndex=0).
    expect(dayHeavenCell.getAttribute("tabindex")).toBe("0");
    dayHeavenCell.focus();
    fireEvent.keyDown(dayHeavenCell, { key: "ArrowRight" });
    const hourHeavenCell = screen.getByTestId("saju-full-cell-천간-hour");
    expect(hourHeavenCell.getAttribute("tabindex")).toBe("0");
  });

  it("AC4: ArrowDown moves focus from 천간 row to 지지 row in the same column", () => {
    render(<SajuFullChart chart={KNOWN_CHART} birthTimeKnown={true} />);
    const dayHeaven = screen.getByTestId("saju-full-cell-천간-day");
    dayHeaven.focus();
    fireEvent.keyDown(dayHeaven, { key: "ArrowDown" });
    const dayEarth = screen.getByTestId("saju-full-cell-지지-day");
    expect(dayEarth.getAttribute("tabindex")).toBe("0");
  });

  it("AC4: Home/End jump to first/last pillar in the current row", () => {
    render(<SajuFullChart chart={KNOWN_CHART} birthTimeKnown={true} />);
    const dayHeaven = screen.getByTestId("saju-full-cell-천간-day");
    dayHeaven.focus();
    fireEvent.keyDown(dayHeaven, { key: "Home" });
    expect(
      screen.getByTestId("saju-full-cell-천간-year").getAttribute("tabindex"),
    ).toBe("0");
    fireEvent.keyDown(screen.getByTestId("saju-full-cell-천간-year"), {
      key: "End",
    });
    expect(
      screen.getByTestId("saju-full-cell-천간-hour").getAttribute("tabindex"),
    ).toBe("0");
  });

  it("AC5: 년주 천간 cell aria-label includes 년주 + heaven+earth + 오행 + 십신", () => {
    render(<SajuFullChart chart={KNOWN_CHART} birthTimeKnown={true} />);
    const yearHeaven = screen.getByTestId("saju-full-cell-천간-year");
    const label = yearHeaven.getAttribute("aria-label") ?? "";
    // AC5 literal example: "년주 천간 무자, 오행 수, 십신 비견" — our
    // payload's 년주 has 오행 수 (matches), but 십신 편재 (not 비견 —
    // that's the day pillar). We assert the *structure*, not the exact
    // example string, so this remains correct for any input chart.
    expect(label).toMatch(/^년주 천간 무자/);
    expect(label).toMatch(/오행 수/);
    expect(label).toMatch(/십신 편재/);
  });

  it("AC2: 시 column with birth_time_known=false has 모름 aria-label", () => {
    render(<SajuFullChart chart={UNKNOWN_HOUR_CHART} birthTimeKnown={false} />);
    const hourHeaven = screen.getByTestId("saju-full-cell-천간-hour");
    expect(hourHeaven.getAttribute("aria-label")).toContain("모름");
  });
});
