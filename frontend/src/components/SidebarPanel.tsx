import { useMemo, useState } from 'react';
import { useAppStore } from '@/store/appStore';
import { LANGUAGE_BY_CODE } from '@/i18n/languages';
import { cn } from '@/lib/cn';

type Tab = 'trust' | 'evidence' | 'session';

export function SidebarPanel() {
  const [tab, setTab] = useState<Tab>('trust');
  const messages = useAppStore((s) => s.messages);
  const selectedLanguage = useAppStore((s) => s.selectedLanguage);
  const sessionSchemeNames = useAppStore((s) => s.sessionSchemeNames);

  const latestAssistant = useMemo(
    () => [...messages].reverse().find((m) => m.role === 'assistant' && m.payload),
    [messages],
  );
  const payload = latestAssistant?.payload;

  const confidence = payload?.confidence ?? 'low';
  const confidenceLabel =
    confidence === 'high' ? 'Verified signal' : confidence === 'medium' ? 'Partial signal' : 'Needs clarification';

  const hint = payload?.next_step ?? 'Ask a question to see confidence, rewritten intent, and evidence signals.';
  const queryDebug = payload?.query_debug;
  const rewrite =
    queryDebug?.original && queryDebug?.rewritten && queryDebug.original !== queryDebug.rewritten
      ? `${queryDebug.original} → ${queryDebug.rewritten}`
      : (queryDebug?.rewritten ?? '—');

  const sources = [...(payload?.sources ?? [])]
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    .slice(0, 3);
  const lang = LANGUAGE_BY_CODE[selectedLanguage];

  return (
    <aside aria-label="Active session" className="card-soft flex flex-col gap-4 p-5">
      <h3 className="text-xl">Evidence panel</h3>
      <div role="tablist" aria-label="Evidence sections" className="flex gap-1 rounded-full bg-[var(--color-surface)] p-1">
        <TabButton active={tab === 'trust'} onClick={() => setTab('trust')}>
          Trust
        </TabButton>
        <TabButton active={tab === 'evidence'} onClick={() => setTab('evidence')}>
          Evidence
        </TabButton>
        <TabButton active={tab === 'session'} onClick={() => setTab('session')}>
          Session
        </TabButton>
      </div>

      {tab === 'trust' && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                'inline-block h-2 w-2 rounded-full',
                confidence === 'high' && 'bg-[var(--color-success)]',
                confidence === 'medium' && 'bg-[var(--color-warn)]',
                confidence === 'low' && 'bg-[var(--color-ink-subtle)]',
              )}
            />
            <span className="text-sm font-medium">{confidenceLabel}</span>
          </div>
          <p className="text-xs text-[var(--color-ink-muted)]">{hint}</p>
          <div>
            <p className="eyebrow mb-1">Query understanding</p>
            <p className="text-sm text-[var(--color-ink)]">{rewrite}</p>
          </div>
        </div>
      )}

      {tab === 'evidence' && (
        <div className="flex flex-col gap-3">
          <p className="eyebrow">Top evidence</p>
          {sources.length === 0 ? (
            <p className="text-sm text-[var(--color-ink-muted)]">
              No evidence yet — ask a question to see matched sources.
            </p>
          ) : (
            <ul className="flex flex-col gap-2.5">
              {sources.map((s, i) => {
                const pct = Math.round(Math.min(1, Math.max(0, s.score ?? 0)) * 100);
                return (
                  <li key={`${s.scheme}-${i}`} className="flex flex-col gap-1">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium text-[var(--color-ink)]">
                        <span className="mr-1.5 text-xs text-[var(--color-ink-subtle)]">#{i + 1}</span>
                        {s.scheme}
                      </span>
                      <span className="text-xs text-[var(--color-ink-muted)]">{pct}%</span>
                    </div>
                    <div className="h-1 overflow-hidden rounded-full bg-[var(--color-surface-2)]">
                      <div className="h-full bg-[var(--color-saffron)]" style={{ width: `${pct}%` }} />
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}

      {tab === 'session' && (
        <div className="flex flex-col gap-3">
          <div>
            <p className="eyebrow mb-1">Language</p>
            <p className="text-sm">
              🇮🇳 {lang?.nativeLabel ?? selectedLanguage}
              {lang && <span className="ml-1 text-xs text-[var(--color-ink-subtle)]">({lang.englishLabel})</span>}
            </p>
          </div>
          <div>
            <p className="eyebrow mb-1.5">Schemes mentioned</p>
            {sessionSchemeNames.length === 0 ? (
              <p className="text-xs text-[var(--color-ink-subtle)]">None yet.</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {sessionSchemeNames.map((n) => (
                  <span
                    key={n}
                    className="rounded-full bg-[var(--color-surface)] px-2.5 py-0.5 text-xs text-[var(--color-ink)]"
                  >
                    {n}
                  </span>
                ))}
              </div>
            )}
          </div>
          <ShareTranscriptButton />
        </div>
      )}
    </aside>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        'flex-1 rounded-full px-3 py-1.5 text-xs font-medium transition-colors',
        active ? 'bg-[var(--color-bg-elevated)] text-[var(--color-ink)] shadow-sm' : 'text-[var(--color-ink-muted)]',
      )}
    >
      {children}
    </button>
  );
}

function ShareTranscriptButton() {
  const messages = useAppStore((s) => s.messages);

  const onShare = () => {
    const lines = messages.map((m) => {
      const speaker =
        m.role === 'user' ? 'You' : m.role === 'moderation' ? 'Notice' : m.role === 'error' ? 'System' : 'Assistant';
      return `${speaker}: ${m.content}`;
    });
    const blob = new Blob([lines.join('\n\n')], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'sahayaksetu-chat.txt';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <button
      type="button"
      onClick={onShare}
      disabled={messages.length === 0}
      className="btn-outline mt-1 text-sm disabled:opacity-50"
    >
      Share conversation
    </button>
  );
}
