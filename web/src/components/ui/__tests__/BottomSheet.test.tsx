import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { axe } from "jest-axe";
import { BottomSheet } from "@/components/ui/BottomSheet";

describe("BottomSheet", () => {
  it("does not render when open=false", () => {
    render(
      <BottomSheet open={false} onClose={() => {}} title="공유">
        body
      </BottomSheet>,
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders with role=dialog + aria-modal + aria-labelledby", () => {
    render(
      <BottomSheet open onClose={() => {}} title="공유">
        body
      </BottomSheet>,
    );
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    const labelId = dialog.getAttribute("aria-labelledby");
    expect(labelId).toBeTruthy();
    expect(document.getElementById(labelId!)).toHaveTextContent("공유");
  });

  it("closes when ESC is pressed", () => {
    const onClose = vi.fn();
    render(
      <BottomSheet open onClose={onClose} title="t">
        body
      </BottomSheet>,
    );
    act(() => {
      fireEvent.keyDown(document, { key: "Escape" });
    });
    expect(onClose).toHaveBeenCalled();
  });

  it("closes when backdrop is clicked", () => {
    const onClose = vi.fn();
    render(
      <BottomSheet open onClose={onClose} title="t">
        body
      </BottomSheet>,
    );
    const backdrop = screen.getByTestId("bottom-sheet-backdrop");
    fireEvent.mouseDown(backdrop, {
      target: backdrop,
      currentTarget: backdrop,
    });
    expect(onClose).toHaveBeenCalled();
  });

  it("dismisses when the user swipes down past the threshold", () => {
    const onClose = vi.fn();
    render(
      <BottomSheet open onClose={onClose} title="t" dismissThreshold={50}>
        body
      </BottomSheet>,
    );
    const panel = screen.getByTestId("bottom-sheet-panel");
    fireEvent.touchStart(panel, { touches: [{ clientY: 100 }] });
    fireEvent.touchMove(panel, { touches: [{ clientY: 200 }] });
    fireEvent.touchEnd(panel);
    expect(onClose).toHaveBeenCalled();
  });

  it("does NOT dismiss on tiny drags below the threshold", () => {
    const onClose = vi.fn();
    render(
      <BottomSheet open onClose={onClose} title="t" dismissThreshold={80}>
        body
      </BottomSheet>,
    );
    const panel = screen.getByTestId("bottom-sheet-panel");
    fireEvent.touchStart(panel, { touches: [{ clientY: 100 }] });
    fireEvent.touchMove(panel, { touches: [{ clientY: 130 }] });
    fireEvent.touchEnd(panel);
    expect(onClose).not.toHaveBeenCalled();
  });

  it("passes axe-core scan with zero AA violations", async () => {
    const { container } = render(
      <BottomSheet open onClose={() => {}} title="공유">
        body
      </BottomSheet>,
    );
    const results = await axe(container);
    expect(results.violations).toEqual([]);
  });
});
