"""Guardrail layers (FR-032 defense in depth).

Layers (per Architecture §7.3):

1. **prompt** — system prompt instructions injected at generation time.
2. **evalset** — release gate exercised against ``tests/fixtures/tone_evalset.json``
   (ISSUE-019).
3. **filter** — runtime deny-list scan on streaming chunks
   (this package, ``denylist.py``).

Each layer is independent; a violation caught at layer N records a
``tone_violation_events`` row tagged with ``layer=<N>`` so the audit
trail can attribute responsibility.
"""
