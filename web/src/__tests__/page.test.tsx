import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import HomePage from "@/app/page";

describe("HomePage", () => {
  it("renders the VoiceSaju headline", () => {
    render(<HomePage />);
    expect(
      screen.getByRole("heading", { level: 1, name: /VoiceSaju/i }),
    ).toBeInTheDocument();
  });
});
