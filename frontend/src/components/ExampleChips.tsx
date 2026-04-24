interface Example {
  label: string;
  query: string;
}

const DEFAULT_EXAMPLES: Example[] = [
  {
    label: 'Farmer in Karnataka →',
    query: 'I am a farmer in Karnataka. What government schemes am I eligible for?',
  },
  {
    label: 'Housing for BPL →',
    query: 'What housing schemes are available for BPL families in India?',
  },
];

interface ExampleChipsProps {
  onPick: (query: string) => void;
  examples?: Example[];
}

export function ExampleChips({ onPick, examples = DEFAULT_EXAMPLES }: ExampleChipsProps) {
  return (
    <div className="flex flex-wrap items-center justify-center gap-2">
      {examples.map((e) => (
        <button
          key={e.label}
          type="button"
          onClick={() => onPick(e.query)}
          className="rounded-full border border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-4 py-2 text-sm text-[var(--color-ink-muted)] transition-colors hover:border-[var(--color-saffron)] hover:text-[var(--color-ink)]"
        >
          <span className="eyebrow mr-2">Try</span>
          {e.label}
        </button>
      ))}
    </div>
  );
}
