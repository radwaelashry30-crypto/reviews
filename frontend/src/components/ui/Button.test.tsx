import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { Button } from "./Button";

describe("Button", () => {
  it("renders children and responds to clicks by default", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Analyze Reviews</Button>);
    fireEvent.click(screen.getByRole("button", { name: "Analyze Reviews" }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("is disabled and unclickable when disabled", () => {
    const onClick = vi.fn();
    render(<Button disabled onClick={onClick}>Analyze Reviews</Button>);
    const button = screen.getByRole("button", { name: "Analyze Reviews" });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("exposes an accessible loading label and stays disabled while loading", () => {
    render(
      <Button loading loadingLabel="Analyzing review">
        Analyze Reviews
      </Button>,
    );
    expect(screen.getByRole("button")).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("Analyzing review");
  });

  it("renders as a react-router Link when `to` is given", () => {
    render(
      <MemoryRouter>
        <Button to="/sentiment">Review Analyzer</Button>
      </MemoryRouter>,
    );
    const link = screen.getByRole("link", { name: "Review Analyzer" });
    expect(link).toHaveAttribute("href", "/sentiment");
  });

  it("renders as an anchor when `href` is given", () => {
    render(<Button href="https://example.com">External</Button>);
    expect(screen.getByRole("link", { name: "External" })).toHaveAttribute("href", "https://example.com");
  });

  it("applies the requested variant class", () => {
    render(<Button variant="destructive">Delete upload</Button>);
    expect(screen.getByRole("button", { name: "Delete upload" })).toHaveClass("bsr-btn--destructive");
  });
});
