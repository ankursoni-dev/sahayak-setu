import { useEffect } from 'react';
import { X } from 'lucide-react';
import { useAppStore } from '@/store/appStore';

export function DebugDrawer() {
  const open = useAppStore((s) => s.debugDrawerOpen);
  const toggle = useAppStore((s) => s.toggleDebugDrawer);
  const traceId = useAppStore((s) => s.lastTraceId);
  const retrievalDebug = useAppStore((s) => s.lastRetrievalDebug);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'd') {
        e.preventDefault();
        toggle();
      }
      if (e.key === 'Escape' && open) toggle(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [toggle, open]);

  return (
    <aside
      aria-hidden={!open}
      aria-label="Retrieval trace"
      className={`fixed right-0 top-0 z-40 h-full w-full max-w-md border-l border-[var(--color-border)] bg-[var(--color-bg-elevated)] shadow-lg transition-transform duration-200 ${open ? 'translate-x-0' : 'translate-x-full'}`}
    >
      <header className="flex items-start justify-between gap-3 border-b border-[var(--color-border)] p-5">
        <div>
          <h3 className="text-lg">Retrieval trace</h3>
          <p className="mt-1 text-xs text-[var(--color-ink-muted)]">
            {traceId ? `Trace ID: ${traceId}` : 'Press Ctrl/Cmd + D after a response'}
          </p>
        </div>
        <button
          type="button"
          onClick={() => toggle(false)}
          aria-label="Close debug"
          className="inline-flex h-8 w-8 items-center justify-center rounded-full text-[var(--color-ink-muted)] hover:bg-[var(--color-surface)]"
        >
          <X size={16} strokeWidth={2} />
        </button>
      </header>
      <pre className="h-[calc(100%-5rem)] overflow-auto p-5 text-xs font-mono text-[var(--color-ink)]">
        {retrievalDebug ? JSON.stringify(retrievalDebug, null, 2) : 'No retrieval debug payload yet.'}
      </pre>
    </aside>
  );
}
