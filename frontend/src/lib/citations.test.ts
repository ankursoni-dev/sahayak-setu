import { describe, it, expect } from 'vitest';
import { stripCitationMarkers, segmentWithCitations, primarySourceIndex } from './citations';

describe('stripCitationMarkers', () => {
  it('removes [n] markers and trims', () => {
    // Matches vanilla behaviour: consumes leading whitespace of each marker only.
    expect(stripCitationMarkers('Apply here [1] and wait [2].')).toBe('Apply here and wait.');
  });

  it('returns empty string for empty input', () => {
    expect(stripCitationMarkers('')).toBe('');
  });
});

describe('segmentWithCitations', () => {
  it('splits text into text and cite segments', () => {
    const segs = segmentWithCitations('Eligible via [1] or [2].', 2);
    expect(segs).toEqual([
      { kind: 'text', value: 'Eligible via ' },
      { kind: 'cite', index: 1 },
      { kind: 'text', value: ' or ' },
      { kind: 'cite', index: 2 },
      { kind: 'text', value: '.' },
    ]);
  });

  it('keeps out-of-range markers as text', () => {
    const segs = segmentWithCitations('Check [5] here.', 2);
    expect(segs.find((s) => s.kind === 'cite')).toBeUndefined();
  });

  it('returns empty array for empty input', () => {
    expect(segmentWithCitations('', 3)).toEqual([]);
  });
});

describe('primarySourceIndex', () => {
  it('returns 0 for empty list', () => {
    expect(primarySourceIndex([])).toBe(0);
  });

  it('returns index of highest score', () => {
    const sources = [{ score: 0.3 }, { score: 0.9 }, { score: 0.6 }];
    expect(primarySourceIndex(sources)).toBe(1);
  });
});
