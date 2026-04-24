export function stripCitationMarkers(text: string): string {
  if (!text) return '';
  return text.replace(/\s*\[\d+\]/g, '').trim();
}

/** Returns the inclusive index (1-based) of the source with the highest score. */
export function primarySourceIndex<T extends { score?: number }>(sources: readonly T[]): number {
  if (!sources.length) return 0;
  let bestIdx = 0;
  let bestScore = -Infinity;
  sources.forEach((s, i) => {
    const score = typeof s.score === 'number' ? s.score : 0;
    if (score > bestScore) {
      bestScore = score;
      bestIdx = i;
    }
  });
  return bestIdx;
}

/** Splits answer text into segments, surfacing [n] citation markers as typed chunks. */
export type TextSegment =
  | { kind: 'text'; value: string }
  | { kind: 'cite'; index: number };

export function segmentWithCitations(text: string, maxIndex: number): TextSegment[] {
  if (!text) return [];
  const out: TextSegment[] = [];
  const re = /\[(\d+)\]/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push({ kind: 'text', value: text.slice(last, m.index) });
    const n = parseInt(m[1]!, 10);
    if (n >= 1 && n <= maxIndex) {
      out.push({ kind: 'cite', index: n });
    } else {
      out.push({ kind: 'text', value: m[0] });
    }
    last = re.lastIndex;
  }
  if (last < text.length) out.push({ kind: 'text', value: text.slice(last) });
  return out;
}
