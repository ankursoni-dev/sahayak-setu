import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ConfidenceArc } from './ConfidenceArc';

describe('ConfidenceArc', () => {
  it('renders verified label for high confidence', () => {
    render(<ConfidenceArc confidence="high" score={0.92} />);
    expect(screen.getByText('VERIFIED')).toBeInTheDocument();
    expect(screen.getByText('0.92 match')).toBeInTheDocument();
  });

  it('renders partial label for medium confidence', () => {
    render(<ConfidenceArc confidence="medium" score={0.55} />);
    expect(screen.getByText('PARTIAL')).toBeInTheDocument();
  });

  it('renders unverified label for low/null confidence', () => {
    render(<ConfidenceArc confidence={null} score={null} />);
    expect(screen.getByText('UNVERIFIED')).toBeInTheDocument();
    expect(screen.getByText('0.00 match')).toBeInTheDocument();
  });

  it('clamps score to [0,1]', () => {
    render(<ConfidenceArc confidence="high" score={1.5} />);
    expect(screen.getByText('1.00 match')).toBeInTheDocument();
  });
});
