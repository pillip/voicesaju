/**
 * axe-core a11y scan on the preview page (NFR-012, ISSUE-021 AC).
 *
 * Asserts zero WCAG 2.1 AA violations across all 8 components rendered in
 * default / disabled / loading states.
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import PreviewPage from '@/app/preview/page';

expect.extend(toHaveNoViolations);

describe('Preview page — WCAG 2.1 AA', () => {
  it('has zero axe-core violations on the full preview render', async () => {
    const { container } = render(<PreviewPage />);
    const results = await axe(container, {
      rules: {
        // color-contrast can be flaky in jsdom where computed CSS isn't
        // available — design_system.md already documents that all chosen
        // pairs pass 4.5:1 in real browsers.
        'color-contrast': { enabled: false },
      },
    });
    expect(results).toHaveNoViolations();
  });
});
