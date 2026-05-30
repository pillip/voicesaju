"use client";

import { cn } from "@/lib/utils";

export interface SubtitleBandProps {
  /** Subtitle text to render. */
  text: string;
  /** Visual tone — `default` for live audio, `static` for the fallback branch. */
  tone?: "default" | "static";
  /** Optional className for the wrapper. */
  className?: string;
  /** Optional testid for the wrapper. */
  "data-testid"?: string;
}

/**
 * Subtitle band used by the intro player (ISSUE-032).
 *
 * Rendered at the bottom 30% of Screen 7 per ux_spec. We keep this component
 * tiny because v2 lands LLM-driven karaoke-style highlighting (separate
 * issue) and we want to be able to drop in that work without untangling
 * complex layout state here.
 *
 * Accessibility:
 *  - `aria-live="polite"` so screen readers re-announce the line when it
 *    changes (e.g. error fallback swap).
 *  - The static tone is reserved for the audio-failure branch where the
 *    subtitle is the only signal — it gets a slight visual de-emphasis to
 *    pair with the "탭해서 듣기" CTA.
 */
export function SubtitleBand({
  text,
  tone = "default",
  className,
  "data-testid": testId,
}: SubtitleBandProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      data-testid={testId}
      className={cn(
        "min-h-[3.5rem] w-full rounded-md px-s4 py-s3 text-center font-body text-base leading-relaxed",
        tone === "default" && "bg-ink-800 text-cream-50",
        tone === "static" && "bg-ink-800/60 text-cream-200",
        className,
      )}
    >
      {text}
    </div>
  );
}
