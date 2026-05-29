import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StepIndicator } from '@/components/ui/StepIndicator';
import { Toast } from '@/components/ui/Toast';
import { Banner } from '@/components/ui/Banner';

describe('StepIndicator', () => {
  it('renders N steps with the active step marked aria-current', () => {
    render(<StepIndicator total={3} current={2} />);
    const steps = screen.getAllByRole('listitem');
    expect(steps).toHaveLength(3);
    expect(steps[1]).toHaveAttribute('aria-current', 'step');
    expect(steps[0]).not.toHaveAttribute('aria-current');
    expect(steps[2]).not.toHaveAttribute('aria-current');
  });

  it('exposes a screen-reader label for the overall progress', () => {
    render(<StepIndicator total={5} current={3} />);
    expect(screen.getByRole('list')).toHaveAttribute('aria-label', '3 / 5');
  });

  it('supports a loading state via aria-busy on the list', () => {
    render(<StepIndicator total={3} current={1} loading />);
    expect(screen.getByRole('list')).toHaveAttribute('aria-busy', 'true');
  });
});

describe('Toast', () => {
  it('renders with role=status and polite live region by default', () => {
    render(<Toast tone="info">저장되었습니다</Toast>);
    const toast = screen.getByRole('status');
    expect(toast).toHaveAttribute('aria-live', 'polite');
    expect(toast).toHaveTextContent('저장되었습니다');
  });

  it('uses role=alert for the error tone', () => {
    render(<Toast tone="error">오류 발생</Toast>);
    const toast = screen.getByRole('alert');
    expect(toast).toHaveTextContent('오류 발생');
  });

  it('renders the loading variant with aria-busy', () => {
    render(
      <Toast tone="info" loading>
        업로드 중
      </Toast>,
    );
    expect(screen.getByRole('status')).toHaveAttribute('aria-busy', 'true');
  });
});

describe('Banner', () => {
  it.each(['info', 'success', 'warning', 'error'] as const)(
    'renders %s tone with semantic role',
    (tone) => {
      render(<Banner tone={tone}>알림</Banner>);
      const banner =
        tone === 'error' || tone === 'warning'
          ? screen.getByRole('alert')
          : screen.getByRole('status');
      expect(banner).toHaveTextContent('알림');
    },
  );

  it('supports a disabled variant (dimmed but visible)', () => {
    render(
      <Banner tone="info" disabled>
        알림
      </Banner>,
    );
    expect(screen.getByRole('status')).toHaveAttribute('aria-disabled', 'true');
  });
});
