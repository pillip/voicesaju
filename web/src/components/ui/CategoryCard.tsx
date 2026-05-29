'use client';

import { forwardRef } from 'react';
import type { ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export type CategoryKey = 'love' | 'work' | 'money' | 'tarot';

export interface CategoryCardProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  category: CategoryKey;
  loading?: boolean;
}

/**
 * Tall card surfacing one of the four v1 categories (연애/직장/금전/타로).
 * Background uses the matching `bg-category-<key>` token. Selecting a card
 * triggers a downstream reading flow — for v1 we render as a <button>.
 */
const CATEGORY_BG: Record<CategoryKey, string> = {
  love: 'bg-category-love',
  work: 'bg-category-work',
  money: 'bg-category-money',
  tarot: 'bg-category-tarot',
};

const CATEGORY_LABEL_KO: Record<CategoryKey, string> = {
  love: '연애',
  work: '직장',
  money: '금전',
  tarot: '타로',
};

export const CategoryCard = forwardRef<HTMLButtonElement, CategoryCardProps>(function CategoryCard(
  { className, category, children, disabled, loading, ...rest },
  ref,
) {
  const isDisabled = disabled || loading;
  return (
    <button
      ref={ref}
      type="button"
      data-testid={`category-card-${category}`}
      aria-label={`${CATEGORY_LABEL_KO[category]} 카테고리 선택`}
      aria-disabled={isDisabled || undefined}
      aria-busy={loading || undefined}
      disabled={isDisabled}
      className={cn(
        'flex aspect-[3/4] w-full flex-col items-start justify-end gap-s2 rounded-md p-s4 text-left transition-transform',
        CATEGORY_BG[category],
        'text-cream-50 hover:scale-[1.01] active:scale-[0.99]',
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300',
        isDisabled && 'cursor-not-allowed opacity-50 hover:scale-100',
        className,
      )}
      {...rest}
    >
      <span className="font-display text-xl">{CATEGORY_LABEL_KO[category]}</span>
      <span className="text-sm text-cream-100">{children}</span>
      {loading && <span className="sr-only">로딩 중</span>}
    </button>
  );
});
