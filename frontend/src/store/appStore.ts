import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { env } from '@/lib/env';
import type { ChatMessage } from '@/types/chat';
import type { UserProfile } from '@/types/agent';
import type { VoiceState, VoiceTransport } from '@/types/voice';

type StatusTone = 'green' | 'orange' | 'red' | 'yellow' | 'blue';

interface PersistedSlice {
  sessionUserId: string;
  selectedLanguage: string;
  lastQuery: string;
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
}

export type AppStore = PersistedSlice & TransientSlice & Actions;

export const useAppStore = create<AppStore>()(
  persist(
    (set) => ({
      sessionUserId: '',
      selectedLanguage: 'hi-IN',
      lastQuery: '',

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
    }),
    {
      name: 'sahayak-app',
      partialize: (s): PersistedSlice => ({
        sessionUserId: s.sessionUserId,
        selectedLanguage: s.selectedLanguage,
        lastQuery: s.lastQuery,
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
