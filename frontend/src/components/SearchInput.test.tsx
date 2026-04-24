import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SearchInput } from './SearchInput';

describe('SearchInput', () => {
  it('submits trimmed query via Enter key', async () => {
    const onSubmit = vi.fn();
    render(<SearchInput onSubmit={onSubmit} />);
    const input = screen.getByRole('searchbox');
    await userEvent.type(input, '  pm kisan  {Enter}');
    expect(onSubmit).toHaveBeenCalledWith('pm kisan');
  });

  it('submits via send button and clears input', async () => {
    const onSubmit = vi.fn();
    render(<SearchInput onSubmit={onSubmit} />);
    const input = screen.getByRole('searchbox');
    await userEvent.type(input, 'housing');
    await userEvent.click(screen.getByRole('button', { name: /send/i }));
    expect(onSubmit).toHaveBeenCalledWith('housing');
    expect(input).toHaveValue('');
  });

  it('does not submit empty whitespace', async () => {
    const onSubmit = vi.fn();
    render(<SearchInput onSubmit={onSubmit} />);
    await userEvent.type(screen.getByRole('searchbox'), '   {Enter}');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('respects disabled prop', async () => {
    const onSubmit = vi.fn();
    render(<SearchInput onSubmit={onSubmit} disabled />);
    await userEvent.type(screen.getByRole('searchbox'), 'hi{Enter}');
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
