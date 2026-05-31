"use client";

/**
 * `<SajuFullChart>` — full 4-pillar 명식 grid for `/me/saju` (Screen 17,
 * ISSUE-064).
 *
 * Why this component exists alongside the existing `<SajuChart>`:
 *   - `<SajuChart>` (ISSUE-042) is the **collapsible reading-screen
 *     sidebar** — column-major, optimized for narrow sidebar layouts,
 *     and exposes only 천간 + 지지 + 오행 in the body. It's reused on
 *     `/reading/play`.
 *   - `<SajuFullChart>` is the **My Page screen-center grid** — a 4-row
 *     × 4-pillar table that displays 천간 / 지지 / 오행 / 십신 as
 *     dedicated rows (per ux_spec Screen 17), with cell-level
 *     aria-labels and arrow-key navigation across the grid (AC4/AC5).
 *
 * Layout (rows × cols = 4 × 4):
 *
 *                  년     월     일     시
 *        천간     무     갑     경     —
 *        지지     자     오     신     —
 *        오행     수     화     금     —
 *        십신     편재   정관   비견   —
 *
 * When `birthTimeKnown=false`, the 시 column collapses to "모름" cells
 * (de-emphasized via `text-cream-500/60`) and the column-level tap
 * shows the dedicated 시간 모름 tooltip.
 *
 * Tooltip:
 *   Per AC3, tapping any non-empty cell shows the 오행 + 십신
 *   explanation for that pillar (we lift it to a *pillar-level* tooltip
 *   rather than a per-row tooltip to avoid four redundant tooltips on
 *   the same column). The tooltip is positioned above the column and
 *   announced via `role="tooltip"` + `aria-describedby` (NFR-013).
 *
 * Arrow-key nav (AC4):
 *   The grid behaves as a single roving-tabindex region with the
 *   currently-focused cell at `tabIndex={0}` and the rest at `-1`.
 *   ArrowLeft/ArrowRight move between pillars (columns). ArrowUp /
 *   ArrowDown move between rows. Home/End jump to the first/last
 *   pillar in the current row. Focus changes also drive the
 *   tooltip pillar so the visible tooltip stays in sync with the
 *   focused cell — that's the user-observable "tooltip focus moves
 *   across the grid" promised by AC4.
 *
 * Screen reader (AC5):
 *   Each cell carries an aria-label of the form
 *   "{pillar_full_label} {row_label} {char}, 오행 {element}, 십신 {tenGod}"
 *   so a row read out loud says e.g.
 *     "년주 천간 무자, 오행 수, 십신 비견" (AC5 example).
 *   The element + tenGod are repeated in every cell of the column
 *   because screen readers traverse cell-by-cell and reading only the
 *   row-specific data would leave the user without context.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  PILLAR_FULL_LABELS,
  PILLAR_LABELS,
  STEM_TO_ELEMENT,
  type HeavenlyStem,
  type PillarKey,
  type WuXing,
} from "@/lib/saju/data";
import type { SajuChartPayload, SajuPillar } from "@/lib/api/profile";
import { cn } from "@/lib/utils";

export interface SajuFullChartProps {
  chart: SajuChartPayload;
  birthTimeKnown: boolean;
}

interface CellSpec {
  pillarKey: PillarKey;
  pillarLabel: string; // "년" / "월" / "일" / "시"
  pillarFullLabel: string; // "년주" / "월주" / "일주" / "시주"
  heaven: string | null;
  earth: string | null;
  element: string | null;
  tenGod: string | null;
  isUnknown: boolean; // 시 column when birthTimeKnown=false
}

interface FocusedCell {
  row: number; // 0..3 — 천간 / 지지 / 오행 / 십신
  col: number; // 0..3 — 년 / 월 / 일 / 시
}

const ROW_LABELS = ["천간", "지지", "오행", "십신"] as const;
const ROW_COUNT = ROW_LABELS.length; // 4
const COLUMN_KEYS: ReadonlyArray<PillarKey> = ["year", "month", "day", "hour"];

/** WuXing color hints — kept tonally muted to match the ink theme. */
const ELEMENT_COLORS: Record<WuXing, string> = {
  목: "text-emerald-300",
  화: "text-rose-300",
  토: "text-amber-300",
  금: "text-slate-200",
  수: "text-sky-300",
};

function getElement(pillar: SajuPillar | null): string | null {
  if (!pillar) return null;
  if (pillar.element) return pillar.element;
  // Fallback: derive from stem if backend omitted the field.
  if ((HEAVENLY_STEMS as readonly string[]).includes(pillar.stem)) {
    return STEM_TO_ELEMENT[pillar.stem as HeavenlyStem];
  }
  return null;
}

// Re-export so the fallback lookup above resolves at runtime.
import { HEAVENLY_STEMS } from "@/lib/saju/data";

function buildCells(
  chart: SajuChartPayload,
  birthTimeKnown: boolean,
): CellSpec[] {
  return COLUMN_KEYS.map((key) => {
    const pillar = chart[key];
    if (key === "hour" && (!pillar || !birthTimeKnown)) {
      return {
        pillarKey: key,
        pillarLabel: PILLAR_LABELS[key],
        pillarFullLabel: PILLAR_FULL_LABELS[key],
        heaven: null,
        earth: null,
        element: null,
        tenGod: null,
        isUnknown: true,
      } as CellSpec;
    }
    if (!pillar) {
      return {
        pillarKey: key,
        pillarLabel: PILLAR_LABELS[key],
        pillarFullLabel: PILLAR_FULL_LABELS[key],
        heaven: null,
        earth: null,
        element: null,
        tenGod: null,
        isUnknown: true,
      } as CellSpec;
    }
    return {
      pillarKey: key,
      pillarLabel: PILLAR_LABELS[key],
      pillarFullLabel: PILLAR_FULL_LABELS[key],
      heaven: pillar.stem,
      earth: pillar.branch,
      element: getElement(pillar),
      tenGod: pillar.ten_god,
      isUnknown: false,
    } as CellSpec;
  });
}

function cellChar(row: number, cell: CellSpec): string | null {
  switch (row) {
    case 0:
      return cell.heaven;
    case 1:
      return cell.earth;
    case 2:
      return cell.element;
    case 3:
      return cell.tenGod;
    default:
      return null;
  }
}

function cellAriaLabel(row: number, cell: CellSpec): string {
  if (cell.isUnknown) {
    return `${cell.pillarFullLabel} ${ROW_LABELS[row]} 모름`;
  }
  const rowChar = cellChar(row, cell) ?? "";
  // Per AC5: every cell announces the pillar context + 오행 + 십신 even
  // if the row itself is e.g. 천간 — so the user always hears the full
  // "년주 천간 무자, 오행 수, 십신 비견" envelope.
  const rowLabel = ROW_LABELS[row];
  const heaven = cell.heaven ?? "";
  const earth = cell.earth ?? "";
  const headerChars = `${heaven}${earth}`;
  const element = cell.element ?? "";
  const tenGod = cell.tenGod ?? "";
  // 천간 row → announce the heaven+earth pair so AC5's literal example
  // ("천간 무자") holds. Other rows announce the row-specific character.
  const announced = row === 0 ? headerChars : rowChar;
  const parts = [
    `${cell.pillarFullLabel} ${rowLabel} ${announced}`,
    element ? `오행 ${element}` : "",
    tenGod ? `십신 ${tenGod}` : "",
  ].filter(Boolean);
  return parts.join(", ");
}

export function SajuFullChart({
  chart,
  birthTimeKnown,
}: SajuFullChartProps): ReactNode {
  const cells = useMemo(
    () => buildCells(chart, birthTimeKnown),
    [chart, birthTimeKnown],
  );
  // Initial focus lands on the 일주 천간 (the "core" pillar in saju
  // reading conventions). row=0 (천간), col=2 (day).
  const [focus, setFocus] = useState<FocusedCell>({ row: 0, col: 2 });
  // Tooltip column is *separate* state: a tooltip is only visible when
  // the user has explicitly activated it (click / Enter / Space). Arrow
  // keys move the focus and — if a tooltip is currently active — also
  // slide it to the new column so AC4 ("tooltip focus moves across the
  // grid") is observable.
  const [activeTooltipCol, setActiveTooltipCol] = useState<number | null>(null);
  const cellRefs = useRef<Array<Array<HTMLButtonElement | null>>>(
    Array.from({ length: ROW_COUNT }, () =>
      Array<HTMLButtonElement | null>(cells.length).fill(null),
    ),
  );

  // Drive actual DOM focus on `focus` changes so arrow-key navigation
  // moves the browser focus, not just the React state.
  useEffect(() => {
    const node = cellRefs.current[focus.row]?.[focus.col];
    if (node && document.activeElement !== node) {
      // We only re-focus if the user is currently inside the grid,
      // otherwise we'd steal focus from elsewhere on the page (e.g.
      // when the page first mounts the chart shouldn't grab focus).
      const active = document.activeElement;
      if (
        active &&
        cellRefs.current.some((row) =>
          row.includes(active as HTMLButtonElement),
        )
      ) {
        node.focus();
      }
    }
  }, [focus]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLButtonElement>, row: number, col: number) => {
      let next: FocusedCell | null = null;
      switch (e.key) {
        case "ArrowLeft":
          next = { row, col: Math.max(0, col - 1) };
          break;
        case "ArrowRight":
          next = { row, col: Math.min(cells.length - 1, col + 1) };
          break;
        case "ArrowUp":
          next = { row: Math.max(0, row - 1), col };
          break;
        case "ArrowDown":
          next = { row: Math.min(ROW_COUNT - 1, row + 1), col };
          break;
        case "Home":
          next = { row, col: 0 };
          break;
        case "End":
          next = { row, col: cells.length - 1 };
          break;
        case "Enter":
        case " ":
          // Toggle tooltip on the current column.
          setActiveTooltipCol((prev) => (prev === col ? null : col));
          e.preventDefault();
          return;
        case "Escape":
          setActiveTooltipCol(null);
          return;
        default:
          return;
      }
      if (next) {
        e.preventDefault();
        setFocus(next);
        // If a tooltip is currently visible, slide it to the new
        // column so arrow-key nav moves "tooltip focus across the
        // grid" (AC4). If no tooltip is active we leave it that way —
        // arrow keys alone don't open one.
        setActiveTooltipCol((prev) => (prev !== null ? next!.col : prev));
      }
    },
    [cells.length],
  );

  const handleClick = useCallback((row: number, col: number) => {
    setFocus({ row, col });
    setActiveTooltipCol((prev) => (prev === col ? null : col));
  }, []);

  const handleBlurGrid = useCallback((e: React.FocusEvent<HTMLDivElement>) => {
    // Close the tooltip when focus exits the grid entirely.
    if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
      setActiveTooltipCol(null);
    }
  }, []);

  return (
    <div
      data-testid="saju-full-chart"
      className="border-cream-700 flex flex-col gap-s3 rounded-md border bg-ink-800/60 p-s4 text-cream-100"
      onBlur={handleBlurGrid}
    >
      <table
        className="w-full table-fixed border-collapse text-center font-body"
        aria-label="사주 명식"
        data-testid="saju-full-chart-table"
      >
        <thead>
          <tr>
            {/* Top-left corner — empty header for the row-label column. */}
            <th
              scope="col"
              className="w-1/6 pb-s2 text-xs text-cream-300"
              aria-hidden="true"
            >
              {/* empty */}
            </th>
            {cells.map((cell) => (
              <th
                key={cell.pillarKey}
                scope="col"
                className={cn(
                  "border-cream-700 border-b pb-s2 font-display text-sm",
                  cell.isUnknown ? "text-cream-500" : "text-cream-200",
                )}
                data-testid={`saju-full-chart-col-${cell.pillarKey}`}
              >
                {cell.pillarLabel}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROW_LABELS.map((rowLabel, rowIdx) => (
            <tr key={rowLabel}>
              <th
                scope="row"
                className="pr-s2 pt-s2 text-left text-xs text-cream-300"
                data-testid={`saju-full-chart-row-${rowLabel}`}
              >
                {rowLabel}
              </th>
              {cells.map((cell, colIdx) => {
                const tooltipId = `saju-full-tooltip-${cell.pillarKey}`;
                const isUnknownCell = cell.isUnknown;
                const isFocused = focus.row === rowIdx && focus.col === colIdx;
                const isTooltipOpen = activeTooltipCol === colIdx;
                const ch = cellChar(rowIdx, cell);
                const elementColor =
                  rowIdx === 2 &&
                  cell.element &&
                  (ELEMENT_COLORS[cell.element as WuXing] ?? "");
                return (
                  <td
                    key={`${rowLabel}-${cell.pillarKey}`}
                    className="relative px-s1 pt-s2"
                  >
                    <button
                      ref={(el) => {
                        cellRefs.current[rowIdx][colIdx] = el;
                      }}
                      type="button"
                      tabIndex={isFocused ? 0 : -1}
                      onClick={() => handleClick(rowIdx, colIdx)}
                      onKeyDown={(e) => handleKeyDown(e, rowIdx, colIdx)}
                      onFocus={() => setFocus({ row: rowIdx, col: colIdx })}
                      aria-label={cellAriaLabel(rowIdx, cell)}
                      aria-describedby={isTooltipOpen ? tooltipId : undefined}
                      aria-expanded={isTooltipOpen}
                      data-testid={`saju-full-cell-${rowLabel}-${cell.pillarKey}`}
                      className={cn(
                        "flex w-full items-center justify-center rounded-md px-s1 py-s2 font-display text-lg transition-colors",
                        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300",
                        isUnknownCell
                          ? "italic text-cream-500/60"
                          : "text-cream-50 hover:bg-ink-700/60",
                        elementColor || "",
                      )}
                    >
                      {isUnknownCell ? "모름" : (ch ?? "—")}
                    </button>
                    {isFocused && isTooltipOpen && (
                      <div
                        id={tooltipId}
                        role="tooltip"
                        data-testid={`saju-full-tooltip-${cell.pillarKey}`}
                        className="border-cream-700 absolute left-1/2 top-full z-10 mt-s1 w-max max-w-[200px] -translate-x-1/2 whitespace-normal rounded-md border bg-ink-900 px-s3 py-s2 text-xs text-cream-100 shadow-lg"
                      >
                        {cell.isUnknown ? (
                          <span data-testid="saju-tooltip-unknown">
                            시간 모름
                          </span>
                        ) : (
                          <>
                            <p className="font-display text-sm text-cream-50">
                              {cell.pillarFullLabel} {cell.heaven}
                              {cell.earth}
                            </p>
                            {cell.element && (
                              <p className="mt-s1 text-cream-200">
                                오행 — {cell.element}
                              </p>
                            )}
                            {cell.tenGod && (
                              <p className="text-cream-200">
                                십신 — {cell.tenGod}
                              </p>
                            )}
                          </>
                        )}
                      </div>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {!birthTimeKnown && (
        <p
          className="text-center text-xs text-cream-400"
          data-testid="saju-full-chart-hour-unknown"
        >
          시 정보가 없어 시주는 표시되지 않아.
        </p>
      )}
    </div>
  );
}
