"""Cross-stack smoke for ISSUE-021 — assert v1 design system tokens are present.

This is a thin Python-side check that verifies the frontend tailwind config
exposes the v1 category color hexes documented in `docs/design_system.md`. It
exists so the sprint checkpoint's `pytest`-based RED/GREEN gates can observe
the frontend change from the repo root without needing to spin up the Node
toolchain. The authoritative test coverage lives in
`web/src/components/ui/__tests__/*.test.tsx` (vitest) and
`web/src/app/preview/__tests__/a11y.test.tsx` (axe-core).
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TAILWIND = REPO_ROOT / "web" / "tailwind.config.ts"


@pytest.fixture(scope="module")
def tailwind_text() -> str:
    assert TAILWIND.exists(), f"missing {TAILWIND}"
    return TAILWIND.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "name,hex_value",
    [
        ("love", "#9B4A4A"),
        ("work", "#3D5266"),
        ("money", "#A67C28"),
        ("tarot", "#5B3A5C"),
    ],
)
def test_category_hex_matches_design_system(
    tailwind_text: str, name: str, hex_value: str
) -> None:
    assert hex_value in tailwind_text, (
        f"category.{name} hex {hex_value} missing from tailwind.config.ts"
    )
    assert name in tailwind_text, f"category key {name!r} missing"


def test_pretendard_font_family_present(tailwind_text: str) -> None:
    assert "Pretendard" in tailwind_text


def test_8_base_components_exist() -> None:
    ui_dir = REPO_ROOT / "web" / "src" / "components" / "ui"
    expected = {
        "PrimaryButton.tsx",
        "SecondaryButton.tsx",
        "TertiaryLink.tsx",
        "CategoryCard.tsx",
        "OptionCard.tsx",
        "StepIndicator.tsx",
        "Toast.tsx",
        "Banner.tsx",
    }
    found = {p.name for p in ui_dir.glob("*.tsx")} if ui_dir.exists() else set()
    missing = expected - found
    assert not missing, f"missing UI component files: {sorted(missing)}"


def test_preview_page_exists() -> None:
    preview = REPO_ROOT / "web" / "src" / "app" / "preview" / "page.tsx"
    assert preview.exists(), "web/src/app/preview/page.tsx must exist"
