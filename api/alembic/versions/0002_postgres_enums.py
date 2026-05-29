"""create postgres enums

Creates the 13 native Postgres enums declared in `docs/data_model.md` §4.1.
Enums are created via raw SQL (`op.execute`) for explicit control of names
and ordering; SQLAlchemy `sa.Enum` is intentionally avoided here so that
downstream model code can attach to existing types via
`postgresql.ENUM(..., create_type=False)`.

Revision ID: 0002_postgres_enums
Revises: 0001_initial
Create Date: 2026-05-29
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_postgres_enums"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


# (name, values) — order is the canonical creation order.
# Authoritative source: docs/data_model.md §4.1.
ENUMS: list[tuple[str, tuple[str, ...]]] = [
    ("gender_enum", ("F", "M")),
    ("category_enum", ("love", "work", "money")),
    (
        "reading_status_enum",
        ("queued", "streaming", "done", "failed", "refunded", "cancelled"),
    ),
    ("tarot_status_enum", ("streaming", "done", "failed")),
    (
        "payment_type_enum",
        ("single", "subscription_initial", "subscription_recurring"),
    ),
    ("payment_method_enum", ("tosspay", "kakaopay")),
    (
        "payment_status_enum",
        ("pending", "paid", "failed", "refunded", "partially_refunded"),
    ),
    (
        "subscription_status_enum",
        ("active", "cancel_at_period_end", "cancelled", "past_due"),
    ),
    (
        "free_token_kind_enum",
        (
            "nonmember_trial",
            "signup_grant",
            "failure_compensation",
            "ops_grant",
        ),
    ),
    ("auth_provider_enum", ("kakao", "apple", "toss")),
    ("character_key_enum", ("nuna", "dosa")),
    ("tone_eval_label_enum", ("ok", "violation")),
    (
        "audit_action_enum",
        (
            "profile_read",
            "profile_update",
            "soft_delete",
            "hard_delete",
            "payment_refund",
            "correction_used",
            "export_data",
        ),
    ),
]


def _quote_values(values: tuple[str, ...]) -> str:
    # Postgres enum values are string literals; values are static and
    # checked-in (no SQL injection surface), but we still single-quote
    # consistently.
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # Enums are Postgres-specific; skip on SQLite/other dialects so
        # smoke tests against non-pg databases remain importable.
        return
    for name, values in ENUMS:
        op.execute(f"CREATE TYPE {name} AS ENUM ({_quote_values(values)})")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    # Reverse order matches dependency-safe teardown (no FK references
    # exist yet because no tables consume these enums until ISSUE-008+).
    for name, _ in reversed(ENUMS):
        op.execute(f"DROP TYPE IF EXISTS {name}")
