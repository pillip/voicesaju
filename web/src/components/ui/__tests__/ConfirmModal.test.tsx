import { describe, expect, it, vi } from "vitest";
import { useState } from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { axe } from "jest-axe";
import { ConfirmModal } from "@/components/ui/ConfirmModal";

function Wrapper({
  onConfirm,
  onClose,
  initialOpen = true,
}: {
  onConfirm?: () => void;
  onClose?: () => void;
  initialOpen?: boolean;
}) {
  const [open, setOpen] = useState(initialOpen);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        open
      </button>
      <ConfirmModal
        open={open}
        onClose={() => {
          setOpen(false);
          onClose?.();
        }}
        onConfirm={onConfirm}
        title="삭제 확인"
        description="정말로 계정을 삭제할까요?"
      />
    </>
  );
}

describe("ConfirmModal", () => {
  it("does not render when closed", () => {
    render(<ConfirmModal open={false} onClose={() => {}} title="x" />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders dialog with aria-labelledby + aria-modal", () => {
    render(<ConfirmModal open onClose={() => {}} title="삭제 확인" />);
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    const labelId = dialog.getAttribute("aria-labelledby");
    expect(labelId).toBeTruthy();
    expect(document.getElementById(labelId!)).toHaveTextContent("삭제 확인");
  });

  it("closes when ESC is pressed", async () => {
    const onClose = vi.fn();
    render(<Wrapper onClose={onClose} />);
    await act(async () => {
      fireEvent.keyDown(document, { key: "Escape" });
    });
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onConfirm and onClose when confirm button is clicked", () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    render(<Wrapper onConfirm={onConfirm} onClose={onClose} />);
    fireEvent.click(screen.getByRole("button", { name: "확인" }));
    expect(onConfirm).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it("traps focus — Tab from last focusable cycles to first", async () => {
    render(<ConfirmModal open onClose={() => {}} title="t" />);
    const dialog = screen.getByRole("dialog");
    const buttons = dialog.querySelectorAll("button");
    expect(buttons.length).toBe(2);
    const [cancel, confirm] = Array.from(buttons) as HTMLButtonElement[];
    // Place focus on the last focusable then Tab forward — should cycle to first.
    confirm.focus();
    expect(document.activeElement).toBe(confirm);
    await act(async () => {
      fireEvent.keyDown(document, { key: "Tab" });
    });
    expect(document.activeElement).toBe(cancel);
    // Shift+Tab from first → wraps to last.
    cancel.focus();
    await act(async () => {
      fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    });
    expect(document.activeElement).toBe(confirm);
  });

  it("passes axe-core scan with zero AA violations", async () => {
    const { container } = render(
      <ConfirmModal
        open
        onClose={() => {}}
        title="삭제 확인"
        description="정말로 계정을 삭제할까요?"
      />,
    );
    const results = await axe(container);
    expect(results.violations).toEqual([]);
  });
});
