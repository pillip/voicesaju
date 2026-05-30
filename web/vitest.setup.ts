import "@testing-library/jest-dom/vitest";

// React Testing Library leaves component DOM mounted between tests
// unless `cleanup()` is called between runs. When a test file mocks
// fetch + renders a page multiple times — as the ISSUE-050 page tests
// do — the leftover trees compound and the vitest worker drifts into
// OOM territory (see ISSUE-042 retro: a page test had to be deleted
// for exactly this reason).
//
// Adding cleanup() in afterEach here means every test file gets the
// safety net for free, without each one having to remember it.
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});
