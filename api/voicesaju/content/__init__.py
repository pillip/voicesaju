"""Content-domain package (ISSUE-056..061).

Houses the post-reading "viral asset" pipeline:

- ``quote_card.extract_quote()`` — LLM-driven (Haiku 4.5) quote line
  extraction from a finished reading, with deterministic 40-char budget
  enforcement + deny-list gate + category fallbacks.
- ``quote_card_service`` (ISSUE-057) — persists the ``quote_cards`` row
  and enqueues the OG bake job.
- ``og_bake`` worker (ISSUE-058) — composites the 1080×1920 PNG.

The domain is named after the future per-domain service boundary
documented in `data_model.md` §scaling — `content/` maps cleanly to a
future "content" microservice without a code reshape.
"""

from __future__ import annotations
