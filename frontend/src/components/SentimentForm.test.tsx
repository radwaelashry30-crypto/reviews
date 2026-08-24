import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SentimentForm } from "./SentimentForm";

describe("SentimentForm", () => {
  it("defaults the ABSA model to CNN2D and includes it in the submitted request", () => {
    const onSubmit = vi.fn();
    render(<SentimentForm onSubmit={onSubmit} loading={false} />);

    fireEvent.change(screen.getByLabelText(/Customer review/i), { target: { value: "Great product, arrived on time." } });
    fireEvent.click(screen.getByRole("button", { name: "Analyze review" }));

    expect(onSubmit).toHaveBeenCalledOnce();
    expect(onSubmit.mock.calls[0][0]).toMatchObject({ absa_model: "cnn2d" });
  });

  it("includes the selected DeBERTa ABSA model when explicitly chosen", () => {
    const onSubmit = vi.fn();
    render(<SentimentForm onSubmit={onSubmit} loading={false} />);

    fireEvent.change(screen.getByLabelText(/ABSA model/i), { target: { value: "deberta" } });
    fireEvent.change(screen.getByLabelText(/Customer review/i), { target: { value: "Great product, arrived on time." } });
    fireEvent.click(screen.getByRole("button", { name: "Analyze review" }));

    expect(onSubmit.mock.calls[0][0]).toMatchObject({ absa_model: "deberta" });
  });

  it("lists CNN2D first and never mentions Fake Review or claims DeBERTa is more accurate", () => {
    render(<SentimentForm onSubmit={vi.fn()} loading={false} />);

    const select = screen.getByLabelText(/ABSA model/i) as HTMLSelectElement;
    const optionLabels = Array.from(select.options).map((o) => o.textContent);

    expect(optionLabels[0]).toMatch(/CNN2D/);
    expect(optionLabels.join(" ")).toMatch(/DeBERTa/);
    expect(optionLabels.join(" ").toLowerCase()).not.toMatch(/more accurate|better|fake review|fake_review/);
    expect(select.value).toBe("cnn2d");
  });
});
