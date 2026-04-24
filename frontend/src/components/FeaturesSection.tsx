const FEATURES = [
  {
    icon: '🧠',
    title: 'Gemini 2.0 Flash',
    body: 'Primary AI reasoning with real-time Pan-India script awareness.',
  },
  {
    icon: '🔍',
    title: 'Qdrant RAG',
    body: 'Knowledge base grounded in verified government scheme metadata.',
  },
  {
    icon: '💬',
    title: 'Active memory',
    body: 'Remembers the conversation session for natural follow-up questions.',
  },
];

export function FeaturesSection() {
  return (
    <section id="features" className="mt-20 scroll-mt-20">
      <p className="eyebrow mb-3 text-center">Why SahayakSetu</p>
      <h2 className="mb-10 text-center text-3xl sm:text-4xl">Grounded. Spoken. In your language.</h2>
      <div className="grid gap-5 sm:grid-cols-3">
        {FEATURES.map((f) => (
          <div key={f.title} className="card-soft flex flex-col gap-2 p-6">
            <span className="text-2xl" aria-hidden="true">
              {f.icon}
            </span>
            <h3 className="text-xl">{f.title}</h3>
            <p className="text-sm text-[var(--color-ink-muted)]">{f.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
