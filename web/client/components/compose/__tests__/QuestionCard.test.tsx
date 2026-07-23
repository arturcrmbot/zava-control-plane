// @vitest-environment jsdom
import { describe, it, expect, vi } from "vitest";
import { render, fireEvent, within } from "@testing-library/react";
import { QuestionCard } from "../QuestionCard";

describe("QuestionCard", () => {
  it("answers with a clicked option", () => {
    const onAnswer = vi.fn();
    const { container } = render(<QuestionCard question={{ request_id: "r1", text: "CFO?", options: ["CFO", "committee"] }} onAnswer={onAnswer} />);
    const view = within(container);
    fireEvent.click(view.getByText("committee"));
    expect(onAnswer).toHaveBeenCalledWith("r1", "committee");
  });

  it("answers with free text", () => {
    const onAnswer = vi.fn();
    const { container } = render(<QuestionCard question={{ request_id: "r1", text: "CFO?", options: [] }} onAnswer={onAnswer} />);
    const view = within(container);
    fireEvent.change(view.getByLabelText("Free-text answer"), { target: { value: "new persona" } });
    fireEvent.click(view.getByText("Send"));
    expect(onAnswer).toHaveBeenCalledWith("r1", "new persona");
  });
});
