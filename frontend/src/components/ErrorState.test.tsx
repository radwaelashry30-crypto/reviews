import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ErrorState } from "./ErrorState";
import { ApiClientError } from "../types/api";

describe("ErrorState", () => {
  it("renders nothing when there is no error", () => {
    const { container } = render(<ErrorState error={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the error code and message for an ApiClientError", () => {
    const error = new ApiClientError(503, { code: "MODEL_NOT_AVAILABLE", message: "BERT is not loaded.", details: {} });
    render(<ErrorState error={error} />);
    expect(screen.getByText(/MODEL_NOT_AVAILABLE/)).toBeInTheDocument();
    expect(screen.getByText(/BERT is not loaded\./)).toBeInTheDocument();
  });

  it("falls back to a generic code for a plain Error", () => {
    render(<ErrorState error={new Error("Something broke")} />);
    expect(screen.getByText(/ERROR/)).toBeInTheDocument();
    expect(screen.getByText(/Something broke/)).toBeInTheDocument();
  });
});
