import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Modal } from "./Modal";

describe("Modal", () => {
  it("renders nothing when closed", () => {
    render(
      <Modal open={false} onClose={vi.fn()} title="Watch how it works">
        content
      </Modal>,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders with correct ARIA wiring when open", () => {
    render(
      <Modal open onClose={vi.fn()} title="Watch how it works" description="A short demo">
        content
      </Modal>,
    );
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAccessibleName("Watch how it works");
    expect(dialog).toHaveAccessibleDescription("A short demo");
  });

  it("calls onClose on Escape", () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Watch how it works">
        content
      </Modal>,
    );
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose on backdrop click but not on content click", () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Watch how it works">
        <button type="button">inside</button>
      </Modal>,
    );
    fireEvent.mouseDown(screen.getByText("inside"));
    expect(onClose).not.toHaveBeenCalled();

    fireEvent.mouseDown(screen.getByRole("dialog").parentElement as Element);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("closes via the header close button", () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Watch how it works">
        content
      </Modal>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Close dialog" }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
