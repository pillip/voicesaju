"use client";

import { cn } from "@/lib/utils";

export type CharacterKey = "nuna" | "dosa";

export interface CharacterIllustrationProps {
  /** Persona key. M2 only ships `nuna`; `dosa` lands with the tarot flow. */
  character: CharacterKey;
  /** Optional className override. */
  className?: string;
  /** Optional testid. */
  "data-testid"?: string;
}

/**
 * Placeholder persona illustration used by Screen 7 (ISSUE-032).
 *
 * The real artwork lands in a follow-up issue. Until then, render a
 * full-screen-friendly tinted block with the persona's hue so the layout
 * locks in. Each persona gets its own background tone:
 *  - `nuna`  → amber (matches the 시니컬 누님 voice tokens in copy_guide).
 *  - `dosa`  → tarot purple (carried forward for the M3 tarot flow).
 *
 * We render an inner glyph (✦ for nuna per copy_guide §5 "Amber dot
 * decoration"; 太 for dosa as a thematic placeholder) so visual reviewers
 * can distinguish the two without the real art.
 */
export function CharacterIllustration({
  character,
  className,
  "data-testid": testId,
}: CharacterIllustrationProps) {
  const palette =
    character === "nuna"
      ? "bg-amber-500/20 text-amber-300 ring-amber-400/40"
      : "bg-category-tarot/20 text-cream-50 ring-category-tarot/40";

  const glyph = character === "nuna" ? "✦" : "太";

  return (
    <div
      data-testid={testId}
      data-character={character}
      role="img"
      aria-label={
        character === "nuna" ? "시니컬 누님 캐릭터" : "노인 도사 캐릭터"
      }
      className={cn(
        "flex aspect-square w-full max-w-[260px] items-center justify-center rounded-pill ring-1",
        palette,
        className,
      )}
    >
      <span aria-hidden className="font-display text-6xl leading-none">
        {glyph}
      </span>
    </div>
  );
}
