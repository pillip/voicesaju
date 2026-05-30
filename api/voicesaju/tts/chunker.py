"""Korean-aware sentence chunker (ISSUE-037).

Splits a stream of LLM-emitted text into sentence-level chunks suitable
for Supertone synthesis. Supertone prosody degrades on sub-sentence
chunks (Architecture §8.2), so the chunker:

1. Honors Korean sentence terminators ``.``, ``?``, ``!`` plus the
   common literary ``..`` and ``…`` (single Unicode codepoint
   ``U+2026``).
2. Caps long unterminated runs at ``DEFAULT_MAX_SENTENCE_CHARS`` (120
   characters) so a stuck LLM stream cannot starve the TTS pipeline.
3. Joins back-to-back terminator clusters (``...``, ``..!``, ``?!``)
   into a single sentence boundary — splitting in the middle of those
   yields nonsense fragments like ``.`` to the synthesizer.

The function is sync + pure to keep it cheap to call in tight loops;
the caller (the LLM-stream → TTS bridge in ISSUE-039) decides whether
to flush partial sentences on stream end.
"""

from __future__ import annotations

# Cap on a single un-terminated chunk. 120 chars roughly matches
# Supertone's recommended sentence budget (Architecture §8.2) and keeps
# the first-chunk latency budget achievable.
DEFAULT_MAX_SENTENCE_CHARS: int = 120

# Codepoints that close a sentence in our Korean copy. The literary
# ellipsis (``…`` U+2026) is included alongside the ASCII forms; the
# guardrail filter (ISSUE-020) already normalises Western punctuation
# so we don't need to handle Unicode quote variants here.
_TERMINATORS: frozenset[str] = frozenset(".?!…")


def _split_with_terminator(
    text: str,
    max_chars: int,
) -> tuple[list[str], str]:
    """Split *text* into completed sentences + a trailing remainder.

    A *completed sentence* is any prefix ending in a terminator from
    ``_TERMINATORS`` (collapsing runs of terminators into one boundary
    — see module docstring). A run that exceeds ``max_chars`` without
    hitting a terminator is force-split at ``max_chars`` so the caller
    can still hand something to TTS.

    Returns ``(sentences, remainder)``. ``remainder`` may be empty.
    """
    sentences: list[str] = []
    buffer = ""

    i = 0
    while i < len(text):
        ch = text[i]
        buffer += ch

        if ch in _TERMINATORS:
            # Greedy-eat any adjacent terminators so "..", "...", "?!"
            # close a single sentence rather than producing dangling
            # fragments.
            j = i + 1
            while j < len(text) and text[j] in _TERMINATORS:
                buffer += text[j]
                j += 1
            sentences.append(buffer)
            buffer = ""
            i = j
            continue

        if len(buffer) >= max_chars:
            # Force-cut: prefer to break on the last whitespace inside
            # the buffer so we don't slice a word in half. If the buffer
            # has no whitespace, slice at ``max_chars`` as a last resort.
            cut = buffer.rfind(" ")
            if cut > 0:
                sentences.append(buffer[:cut])
                buffer = buffer[cut + 1 :]
            else:
                sentences.append(buffer)
                buffer = ""

        i += 1

    return sentences, buffer


def chunk_sentences(
    text: str,
    max_chars: int = DEFAULT_MAX_SENTENCE_CHARS,
) -> list[str]:
    """Split *text* into sentence-level chunks suitable for TTS.

    Args:
        text: Raw text to split. May contain mixed Korean + ASCII
            punctuation.
        max_chars: Per-chunk cap. Defaults to
            ``DEFAULT_MAX_SENTENCE_CHARS`` (120). The caller can lower
            this for tighter first-chunk latency budgets.

    Returns:
        A list of trimmed sentence chunks in source order. Empty input
        yields ``[]``. A trailing unterminated remainder is included as
        the final chunk so partial sentences are not lost; the caller
        decides whether to flush it.
    """
    if not text:
        return []

    sentences, remainder = _split_with_terminator(text, max_chars=max_chars)
    if remainder.strip():
        sentences.append(remainder)

    # Strip outer whitespace per chunk; the LLM stream usually leaves
    # leading spaces after a terminator (e.g. ". 다음 문장"). Drop empty
    # results introduced by back-to-back whitespace runs.
    cleaned = [s.strip() for s in sentences]
    return [s for s in cleaned if s]


def split_buffer(
    text: str,
    max_chars: int = DEFAULT_MAX_SENTENCE_CHARS,
) -> tuple[list[str], str]:
    """Streaming-friendly variant: return ``(completed, remainder)``.

    Unlike :func:`chunk_sentences`, this function does **not** flush
    the unterminated trailing fragment — it returns it as the second
    element of the tuple so streaming callers can keep buffering. This
    is the helper the :class:`SupertoneClient` uses to bridge LLM
    stream fragments → sentence boundaries without losing inter-frame
    whitespace.

    Completed sentences are returned trimmed; the remainder is
    returned verbatim so caller-side concatenation does not lose
    spaces at fragment seams (e.g. ``"오늘의 사주는 "`` + ``"전반적
    으로 좋아요."`` correctly produces ``"오늘의 사주는 전반적으로
    좋아요."`` instead of joining as ``"오늘의 사주는전반적..."``).
    """
    if not text:
        return [], ""
    completed, remainder = _split_with_terminator(text, max_chars=max_chars)
    cleaned = [s.strip() for s in completed]
    return [s for s in cleaned if s], remainder


__all__ = [
    "DEFAULT_MAX_SENTENCE_CHARS",
    "chunk_sentences",
    "split_buffer",
]
