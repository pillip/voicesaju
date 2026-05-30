"use client";

/**
 * `<ShareButtonRow>` — Screen 11 share row used by `/reading/end`
 * (ISSUE-059, FR-019).
 *
 * Channel matrix (FR-024):
 *   - `web`         → 3 buttons: 인스타 스토리 (native Web Share API),
 *                     카톡 (KakaoTalk SDK stub), 저장 (download).
 *   - `toss_webview`→ 2 buttons: 저장 + 링크 복사 (clipboard).
 *     Toss's webview policy restricts the system share sheet; per
 *     ux_spec Screen 11 the constrained options are 이미지 저장 +
 *     링크 복사.
 *
 * Web Share API:
 *   - Feature-detect via `typeof navigator.share === 'function'`.
 *   - When unavailable in the `web` channel we still show the button;
 *     the click handler falls back to clipboard + toast (copy_guide
 *     §9 "Error: 인스타 share API 미지원").
 *
 * KakaoTalk SDK:
 *   - The real SDK loads via a `<script>` tag added in the platform
 *     bootstrap (separate issue / DEP-XX). At runtime we just look for
 *     `window.Kakao.Share.sendDefault`. If the global is missing we
 *     show the toast from copy_guide §9 ("카톡 공유 안 되네. 링크 복사할게.")
 *     and fall back to the clipboard.
 *
 * Image download:
 *   - We fetch `/api/og/{slug}` as a blob and create a transient
 *     `<a download="quote-{slug}.png">` to trigger the save. The OG
 *     image is 1080×1920 (per ISSUE-058/060) so the saved file matches
 *     the Instagram-story aspect ratio out of the box.
 *
 * Architecture-Ref: docs/ux_spec.md Screen 11, docs/copy_guide.md §9.
 */

import { useCallback, useState } from "react";
import { useRuntimeContext } from "@/lib/context/runtime-context";
import { cn } from "@/lib/utils";

export interface ShareButtonRowProps {
  /** Share slug (drives the filename + share URL). */
  slug: string;
  /**
   * Absolute or path-relative URL pointing at `/share/{slug}`. The
   * native share sheet + Kakao SDK + clipboard fallback all reference
   * this URL.
   */
  shareUrl: string;
  /** Path to the OG image — usually `/api/og/{slug}`. */
  ogImageUrl: string;
  /** Quote text used for the share-sheet `text` field + Kakao body. */
  quoteText: string;
  /** Optional override for the toast handler (test hook). */
  onToast?: (message: string) => void;
  className?: string;
}

/** copy_guide §9 share-row labels (Korean strings — do not edit). */
const LABEL_INSTAGRAM = "인스타 스토리";
const LABEL_KAKAO = "카톡";
const LABEL_SAVE = "저장";
const LABEL_COPY_LINK = "링크 복사";

const TOAST_NO_INSTAGRAM =
  "이 브라우저는 인스타 직공유가 안 돼. 저장해서 올려줘.";
const TOAST_NO_KAKAO = "카톡 공유 안 되네. 링크 복사할게.";
const TOAST_COPIED = "링크 복사됨.";

/** Resolve the absolute share URL so the share sheet shows the host. */
function absoluteShareUrl(path: string): string {
  if (typeof window === "undefined") return path;
  try {
    return new URL(path, window.location.origin).toString();
  } catch {
    return path;
  }
}

/** Best-effort clipboard write. Returns true on success. */
async function writeClipboard(text: string): Promise<boolean> {
  if (typeof navigator === "undefined") return false;
  const clip = (navigator as Navigator).clipboard;
  if (!clip || typeof clip.writeText !== "function") return false;
  try {
    await clip.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/** Trigger a browser download by synthesising a transient anchor. */
function triggerDownload(href: string, filename: string): void {
  if (typeof document === "undefined") return;
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  // `target="_blank"` so the browser doesn't try to navigate the
  // current document if the `download` attribute is ignored
  // (mostly older mobile Safari). The href is same-origin so popup
  // blockers don't fire.
  a.target = "_blank";
  a.rel = "noopener";
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

export function ShareButtonRow({
  slug,
  shareUrl,
  ogImageUrl,
  quoteText,
  onToast,
  className,
}: ShareButtonRowProps) {
  const { channel, capabilities } = useRuntimeContext();
  const [busy, setBusy] = useState<"idle" | "sharing" | "saving" | "copying">(
    "idle",
  );
  const [toast, setToast] = useState<string | null>(null);

  const showToast = useCallback(
    (msg: string) => {
      if (onToast) {
        onToast(msg);
        return;
      }
      setToast(msg);
      // Auto-dismiss after 3s.
      window.setTimeout(() => setToast(null), 3000);
    },
    [onToast],
  );

  // -----------------------------------------------------------------
  // Native share (인스타 스토리)
  // -----------------------------------------------------------------
  const handleInstagram = useCallback(async () => {
    setBusy("sharing");
    try {
      const url = absoluteShareUrl(shareUrl);
      const nav = navigator as Navigator & {
        share?: (data: ShareData) => Promise<void>;
      };
      if (typeof nav.share === "function") {
        await nav.share({ title: "VoiceSaju", text: quoteText, url });
      } else {
        // Fallback: clipboard + toast.
        const ok = await writeClipboard(url);
        showToast(ok ? TOAST_COPIED : TOAST_NO_INSTAGRAM);
      }
    } catch {
      // User cancelled or share failed — silent (per Web Share API UX
      // norms). No toast: the system sheet already provided feedback.
    } finally {
      setBusy("idle");
    }
  }, [quoteText, shareUrl, showToast]);

  // -----------------------------------------------------------------
  // KakaoTalk (카톡)
  // -----------------------------------------------------------------
  const handleKakao = useCallback(async () => {
    setBusy("sharing");
    try {
      const url = absoluteShareUrl(shareUrl);
      const kakao = (
        window as unknown as {
          Kakao?: {
            Share?: { sendDefault: (payload: KakaoSharePayload) => void };
          };
        }
      ).Kakao;
      if (kakao?.Share?.sendDefault) {
        kakao.Share.sendDefault({
          objectType: "feed",
          content: {
            title: "VoiceSaju",
            description: quoteText,
            imageUrl: absoluteShareUrl(ogImageUrl),
            link: {
              mobileWebUrl: url,
              webUrl: url,
            },
          },
        });
      } else {
        const ok = await writeClipboard(url);
        showToast(ok ? TOAST_COPIED : TOAST_NO_KAKAO);
      }
    } catch {
      showToast(TOAST_NO_KAKAO);
    } finally {
      setBusy("idle");
    }
  }, [ogImageUrl, quoteText, shareUrl, showToast]);

  // -----------------------------------------------------------------
  // Image save (저장)
  // -----------------------------------------------------------------
  const handleSave = useCallback(() => {
    setBusy("saving");
    try {
      triggerDownload(ogImageUrl, `quote-${slug}.png`);
    } finally {
      setBusy("idle");
    }
  }, [ogImageUrl, slug]);

  // -----------------------------------------------------------------
  // Clipboard (Toss-only "링크 복사")
  // -----------------------------------------------------------------
  const handleCopyLink = useCallback(async () => {
    setBusy("copying");
    try {
      const url = absoluteShareUrl(shareUrl);
      const ok = await writeClipboard(url);
      showToast(ok ? TOAST_COPIED : TOAST_NO_INSTAGRAM);
    } finally {
      setBusy("idle");
    }
  }, [shareUrl, showToast]);

  const isToss = channel === "toss_webview";
  // `capabilities` lets us hide buttons even outside Toss (e.g., a
  // browser without `navigator.share` and without Kakao SDK can still
  // surface the buttons — but the click handlers gracefully fall back).
  // For now we only treat the channel signal as authoritative for the
  // button set; capabilities feed the disabled/aria-disabled state.
  const showInstagram = !isToss && capabilities.canShareInstagram;
  const showKakao = !isToss && capabilities.canShareKakao;
  const showCopyLink = isToss;

  return (
    <div
      role="group"
      aria-label="명대사 카드 공유"
      className={cn(
        "flex w-full max-w-md flex-row items-center justify-center gap-s3",
        className,
      )}
    >
      {showInstagram && (
        <button
          type="button"
          onClick={handleInstagram}
          disabled={busy === "sharing"}
          aria-busy={busy === "sharing" || undefined}
          className={SHARE_BTN_CLASS}
          data-testid="share-instagram"
        >
          {LABEL_INSTAGRAM}
        </button>
      )}
      {showKakao && (
        <button
          type="button"
          onClick={handleKakao}
          disabled={busy === "sharing"}
          aria-busy={busy === "sharing" || undefined}
          className={SHARE_BTN_CLASS}
          data-testid="share-kakao"
        >
          {LABEL_KAKAO}
        </button>
      )}
      <button
        type="button"
        onClick={handleSave}
        disabled={busy === "saving"}
        aria-busy={busy === "saving" || undefined}
        className={SHARE_BTN_CLASS}
        data-testid="share-save"
      >
        {LABEL_SAVE}
      </button>
      {showCopyLink && (
        <button
          type="button"
          onClick={handleCopyLink}
          disabled={busy === "copying"}
          aria-busy={busy === "copying" || undefined}
          className={SHARE_BTN_CLASS}
          data-testid="share-copy-link"
        >
          {LABEL_COPY_LINK}
        </button>
      )}
      {toast && (
        <div
          role="status"
          aria-live="polite"
          className="sr-only"
          data-testid="share-toast"
        >
          {toast}
        </div>
      )}
    </div>
  );
}

const SHARE_BTN_CLASS = cn(
  "inline-flex min-w-[88px] items-center justify-center gap-s2 rounded-md px-s4 py-s2 font-body text-sm font-medium",
  "border border-cream-300 bg-transparent text-cream-100 transition-colors",
  "hover:bg-ink-700 active:bg-ink-600",
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300",
  "disabled:cursor-not-allowed disabled:opacity-50",
);

/**
 * Shape passed to `Kakao.Share.sendDefault()`. We type just the fields
 * we use; the full SDK schema lives in the Kakao docs (DEP-XX).
 */
interface KakaoSharePayload {
  objectType: "feed";
  content: {
    title: string;
    description: string;
    imageUrl: string;
    link: {
      mobileWebUrl: string;
      webUrl: string;
    };
  };
}
