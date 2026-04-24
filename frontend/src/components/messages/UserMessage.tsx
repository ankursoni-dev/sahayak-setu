interface UserMessageProps {
  content: string;
}

export function UserMessage({ content }: UserMessageProps) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] rounded-2xl rounded-tr-md bg-[var(--color-cta)] px-4 py-2.5 text-[var(--color-cta-ink)]">
        <p className="whitespace-pre-wrap text-sm">{content}</p>
      </div>
    </div>
  );
}
