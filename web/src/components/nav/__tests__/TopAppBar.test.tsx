import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { TopAppBar } from "@/components/nav/TopAppBar";

describe("TopAppBar", () => {
  it("renders a banner landmark", () => {
    render(<TopAppBar title="사주" />);
    expect(screen.getByRole("banner")).toBeInTheDocument();
  });

  it("renders title as an h1 when given a string", () => {
    render(<TopAppBar title="결과 보기" />);
    expect(
      screen.getByRole("heading", { name: "결과 보기" }),
    ).toBeInTheDocument();
  });

  it("renders back and action slots when provided", () => {
    render(
      <TopAppBar
        back={<button type="button">뒤로</button>}
        title="설정"
        action={<button type="button">완료</button>}
      />,
    );
    expect(screen.getByRole("button", { name: "뒤로" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "완료" })).toBeInTheDocument();
  });

  it("omits back/action when not provided", () => {
    render(<TopAppBar title="홈" />);
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });

  it("passes axe-core scan with zero AA violations", async () => {
    const { container } = render(
      <TopAppBar
        back={<button type="button">뒤로</button>}
        title="설정"
        action={<button type="button">완료</button>}
      />,
    );
    const results = await axe(container);
    expect(results.violations).toEqual([]);
  });
});
