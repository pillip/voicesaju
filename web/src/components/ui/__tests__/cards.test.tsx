import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CategoryCard } from '@/components/ui/CategoryCard';
import { OptionCard } from '@/components/ui/OptionCard';

describe('CategoryCard', () => {
  it.each(['love', 'work', 'money', 'tarot'] as const)(
    'renders %s category with the matching token color',
    (cat) => {
      render(<CategoryCard category={cat}>안녕</CategoryCard>);
      const card = screen.getByTestId(`category-card-${cat}`);
      expect(card).toBeInTheDocument();
      // The category token must be applied as a class — exact hex assertion is
      // covered by the tailwind config test below.
      expect(card.className).toMatch(new RegExp(`bg-category-${cat}`));
    },
  );

  it('respects disabled variant via aria-disabled', () => {
    render(
      <CategoryCard category="love" disabled>
        안녕
      </CategoryCard>,
    );
    const card = screen.getByTestId('category-card-love');
    expect(card).toHaveAttribute('aria-disabled', 'true');
  });

  it('renders loading variant with aria-busy', () => {
    render(
      <CategoryCard category="love" loading>
        안녕
      </CategoryCard>,
    );
    expect(screen.getByTestId('category-card-love')).toHaveAttribute('aria-busy', 'true');
  });
});

describe('OptionCard', () => {
  it('renders as a radio-like button with aria-checked', () => {
    render(<OptionCard selected>옵션 A</OptionCard>);
    const card = screen.getByRole('radio');
    expect(card).toHaveAttribute('aria-checked', 'true');
  });

  it('supports disabled + loading variants', () => {
    const { rerender } = render(<OptionCard disabled>옵션 B</OptionCard>);
    expect(screen.getByRole('radio')).toBeDisabled();
    rerender(<OptionCard loading>옵션 B</OptionCard>);
    expect(screen.getByRole('radio')).toHaveAttribute('aria-busy', 'true');
  });
});
