import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PrimaryButton } from '@/components/ui/PrimaryButton';
import { SecondaryButton } from '@/components/ui/SecondaryButton';
import { TertiaryLink } from '@/components/ui/TertiaryLink';

describe('PrimaryButton', () => {
  it('renders default variant with accessible label', () => {
    render(<PrimaryButton>확인</PrimaryButton>);
    const btn = screen.getByRole('button', { name: '확인' });
    expect(btn).toBeInTheDocument();
    expect(btn).not.toBeDisabled();
    expect(btn).toHaveAttribute('type', 'button');
  });

  it('renders disabled variant with aria-disabled', () => {
    render(<PrimaryButton disabled>확인</PrimaryButton>);
    const btn = screen.getByRole('button', { name: '확인' });
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute('aria-disabled', 'true');
  });

  it('renders loading variant with aria-busy and announces state', () => {
    render(<PrimaryButton loading>저장</PrimaryButton>);
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('aria-busy', 'true');
    expect(btn).toBeDisabled();
    // Visible spinner or "Loading" SR-only text must exist for SR users
    expect(btn).toHaveTextContent(/저장|로딩|loading/i);
  });

  it('matches snapshot for the three variants', () => {
    const { container } = render(
      <>
        <PrimaryButton>default</PrimaryButton>
        <PrimaryButton disabled>disabled</PrimaryButton>
        <PrimaryButton loading>loading</PrimaryButton>
      </>,
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});

describe('SecondaryButton', () => {
  it('renders default + disabled + loading', () => {
    render(
      <>
        <SecondaryButton>취소</SecondaryButton>
        <SecondaryButton disabled>취소</SecondaryButton>
        <SecondaryButton loading>취소</SecondaryButton>
      </>,
    );
    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(3);
    expect(buttons[1]).toBeDisabled();
    expect(buttons[2]).toHaveAttribute('aria-busy', 'true');
  });
});

describe('TertiaryLink', () => {
  it('renders as a link with href', () => {
    render(<TertiaryLink href="/terms">약관</TertiaryLink>);
    const link = screen.getByRole('link', { name: '약관' });
    expect(link).toHaveAttribute('href', '/terms');
  });

  it('supports aria-disabled when disabled', () => {
    render(
      <TertiaryLink href="/terms" disabled>
        약관
      </TertiaryLink>,
    );
    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('aria-disabled', 'true');
    expect(link).toHaveAttribute('tabindex', '-1');
  });
});
