"""Toss Payments client + checkout/confirm routes (ISSUE-044).

Phase-1 wiring: the structural client + routes ship now backed by the
M1 ``MockPaymentAdapter`` (ISSUE-099) so the full M2 payment flow
exercises end-to-end without a real Toss merchant account. The real
HTTP path lands with ISSUE-043.
"""

from __future__ import annotations
