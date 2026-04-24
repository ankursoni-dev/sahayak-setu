import { useState, type FormEvent, type KeyboardEvent } from 'react';
import { ArrowRight } from 'lucide-react';

interface SearchInputProps {
  onSubmit: (query: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function SearchInput({ onSubmit, disabled, placeholder }: SearchInputProps) {
  const [value, setValue] = useState('');

  const commit = () => {
    const q = value.trim();
    if (!q || disabled) return;
    onSubmit(q);
    setValue('');
  };

  const onFormSubmit = (e: FormEvent) => {
    e.preventDefault();
    commit();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      commit();
    }
  };

  return (
    <form
      onSubmit={onFormSubmit}
      role="search"
      className="flex items-center gap-2 rounded-full border border-[var(--color-border-strong)] bg-[var(--color-bg-elevated)] p-1.5 pl-5 shadow-sm focus-within:border-[var(--color-ink)] focus-within:shadow-md transition-all"
    >
      <input
        type="search"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKeyDown}
        disabled={disabled}
        placeholder={placeholder ?? 'Type in any language…'}
        aria-label="Ask about government schemes"
        autoComplete="off"
        className="min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-[var(--color-ink-subtle)]"
      />
      <button
        type="submit"
        disabled={disabled || !value.trim()}
        aria-label="Send"
        className="inline-flex h-10 w-10 flex-none items-center justify-center rounded-full bg-[var(--color-cta)] text-[var(--color-cta-ink)] transition-transform hover:scale-105 disabled:opacity-40 disabled:hover:scale-100"
      >
        <ArrowRight size={18} strokeWidth={2} />
      </button>
    </form>
  );
}
