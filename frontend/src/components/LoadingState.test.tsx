import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LoadingState } from "./LoadingState";

describe("LoadingState", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("shows the label immediately, without the slow-server hint", () => {
    render(<LoadingState label="Classifying..." />);
    expect(screen.getByText("Classifying...")).toBeInTheDocument();
    expect(screen.queryByText(/waking up from idle/)).not.toBeInTheDocument();
  });

  it("shows the cold-start hint after 4 seconds", () => {
    render(<LoadingState />);
    expect(screen.queryByText(/waking up from idle/)).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(4000));
    expect(screen.getByText(/waking up from idle/)).toBeInTheDocument();
  });
});
