import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { env } from '@/lib/env';
import type { ChatMessage } from '@/types/chat';
import type { UserProfile } from '@/types/agent';
import type { VoiceState, VoiceTransport } from '@/types/voice';

type StatusTone = 'green' | 'orange' | 'red' | 'yellow' | 'blue';

/**
 * One scheme the user was shown in a prior session. Persisted across reloads so the
 * outcome prompt can ask "Did you apply for X?" on the next visit. Resolved entries
 * stay in the list (with `resolvedAt` set) so we don't ask the same question twice.
 */
export interface PendingOutcome {
  scheme: string;
  trace_id: string | null;
  /** ms-since-epoch when the user was shown this scheme. */
  ts: number;
  /** ms-since-epoch when the user answered the prompt; absent until then. */
  resolvedAt?: number;
}

const PENDING_OUTCOME_LIMIT = 12;
/** Don't pester the user immediately — wait at least this long before prompting. */
const PENDING_OUTCOME_MIN_AGE_MS = 6 * 60 * 60 * 1000; // 6 hours

interface PersistedSlice {
  sessionUserId: string;
  selectedLanguage: string;
  lastQuery: string;
  pendingOutcomes: PendingOutcome[];
}

interface TransientSlice {
  messages: ChatMessage[];
  typing: boolean;
  statusText: string;
  statusTone: StatusTone;
  voiceState: VoiceState;
  voiceTransport: VoiceTransport;
  voiceLiveCaption: string;
  searchInFlight: boolean;
  sessionSchemeNames: string[];
  lastTraceId: string | null;
  lastRetrievalDebug: Record<string, unknown> | null;
  lastFinderProfile: Partial<UserProfile> | null;
  debugDrawerOpen: boolean;
}

interface Actions {
  setSessionUserId: (id: string) => void;
  setLanguage: (code: string) => void;
  setLastQuery: (query: string) => void;
  appendMessage: (msg: ChatMessage) => void;
  clearMessages: () => void;
  setTyping: (on: boolean) => void;
  setStatus: (text: string, tone: StatusTone) => void;
  setVoice: (patch: Partial<Pick<TransientSlice, 'voiceState' | 'voiceTransport' | 'voiceLiveCaption'>>) => void;
  setSearchInFlight: (v: boolean) => void;
  recordSchemes: (names: string[]) => void;
  setTrace: (traceId: string | null, retrievalDebug: Record<string, unknown> | null) => void;
  setFinderProfile: (p: Partial<UserProfile> | null) => void;
  toggleDebugDrawer: (force?: boolean) => void;
  recordPendingOutcomes: (schemes: string[], traceId: string | null) => void;
  resolvePendingOutcome: (scheme: string) => void;
  /** Pending outcome eligible for prompting right now (oldest unresolved + past min age). */
  nextPromptableOutcome: () => PendingOutcome | null;
}

export type AppStore = PersistedSlice & TransientSlice & Actions;

export const useAppStore = create<AppStore>()(
  persist(
    (set, get) => ({
      sessionUserId: '',
      selectedLanguage: 'hi-IN',
      lastQuery: '',
      pendingOutcomes: [],

      messages: [],
      typing: false,
      statusText: 'Ready',
      statusTone: 'green',
      voiceState: 'idle',
      voiceTransport: 'none',
      voiceLiveCaption: '',
      searchInFlight: false,
      sessionSchemeNames: [],
      lastTraceId: null,
      lastRetrievalDebug: null,
      lastFinderProfile: null,
      debugDrawerOpen: false,

      setSessionUserId: (id) => set({ sessionUserId: id }),
      setLanguage: (code) => set({ selectedLanguage: code }),
      setLastQuery: (query) => set({ lastQuery: query }),
      appendMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
      clearMessages: () => set({ messages: [] }),
      setTyping: (on) => set({ typing: on }),
      setStatus: (text, tone) => set({ statusText: text, statusTone: tone }),
      setVoice: (patch) => set(patch),
      setSearchInFlight: (v) => set({ searchInFlight: v }),
      recordSchemes: (names) =>
        set((s) => {
          const existing = new Set(s.sessionSchemeNames);
          names.forEach((n) => n && existing.add(n));
          return { sessionSchemeNames: Array.from(existing) };
        }),
      setTrace: (traceId, retrievalDebug) => set({ lastTraceId: traceId, lastRetrievalDebug: retrievalDebug }),
      setFinderProfile: (p) => set({ lastFinderProfile: p }),
      toggleDebugDrawer: (force) =>
        set((s) => ({ debugDrawerOpen: typeof force === 'boolean' ? force : !s.debugDrawerOpen })),
      recordPendingOutcomes: (schemes, traceId) =>
        set((s) => {
          const now = Date.now();
          // Only record schemes we haven't already captured (resolved or unresolved).
          const known = new Set(s.pendingOutcomes.map((p) => p.scheme.toLowerCase()));
          const additions: PendingOutcome[] = [];
          for (const name of schemes) {
            const trimmed = (name ?? '').trim();
            if (!trimmed) continue;
            if (known.has(trimmed.toLowerCase())) continue;
            additions.push({ scheme: trimmed, trace_id: traceId, ts: now });
            known.add(trimmed.toLowerCase());
          }
          if (!additions.length) return s;
          const merged = [...s.pendingOutcomes, ...additions];
          // Keep the list bounded — drop oldest *resolved* first, then oldest unresolved.
          if (merged.length <= PENDING_OUTCOME_LIMIT) return { pendingOutcomes: merged };
          merged.sort((a, b) => {
            if (Boolean(a.resolvedAt) !== Boolean(b.resolvedAt)) {
              return a.resolvedAt ? -1 : 1;
            }
            return a.ts - b.ts;
          });
          return { pendingOutcomes: merged.slice(merged.length - PENDING_OUTCOME_LIMIT) };
        }),
      resolvePendingOutcome: (scheme) =>
        set((s) => ({
          pendingOutcomes: s.pendingOutcomes.map((p) =>
            p.scheme.toLowerCase() === scheme.toLowerCase() && !p.resolvedAt
              ? { ...p, resolvedAt: Date.now() }
              : p,
          ),
        })),
      nextPromptableOutcome: () => {
        const now = Date.now();
        const eligible = get().pendingOutcomes
          .filter((p) => !p.resolvedAt && now - p.ts >= PENDING_OUTCOME_MIN_AGE_MS)
          .sort((a, b) => a.ts - b.ts);
        return eligible[0] ?? null;
      },
    }),
    {
      name: 'sahayak-app',
      partialize: (s): PersistedSlice => ({
        sessionUserId: s.sessionUserId,
        selectedLanguage: s.selectedLanguage,
        lastQuery: s.lastQuery,
        pendingOutcomes: s.pendingOutcomes,
      }),
      storage: {
        getItem: (name) => {
          try {
            const raw = localStorage.getItem(name);
            return raw ? JSON.parse(raw) : null;
          } catch {
            return null;
          }
        },
        setItem: (name, value) => {
          try {
            localStorage.setItem(name, JSON.stringify(value));
          } catch {
            // storage may be full or unavailable (private mode) — ignore
          }
        },
        removeItem: (name) => {
          try {
            localStorage.removeItem(name);
          } catch {
            // ignore
          }
        },
      },
    },
  ),
);

/** Default initial session user id lookup helper for legacy key (migration path). */
export function readLegacySessionUserId(): string {
  try {
    return localStorage.getItem(env.SESSION_USER_ID_KEY) ?? '';
  } catch {
    return '';
  }
}
