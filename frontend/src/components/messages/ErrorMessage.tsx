interface ErrorMessageProps {
  content: string;
}

export function ErrorMessage({ content }: ErrorMessageProps) {
  return (
    <div
      role="alert"
      className="rounded-2xl border border-[var(--color-error)]/30 bg-[var(--color-error)]/10 p-3 text-sm text-[var(--color-error)]"
    >
      {content || 'Something went wrong.'}
    </div>
  );
}
