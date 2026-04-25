import { useCallback } from 'react';
import { searchSchemes, reportError, mapNetworkErrorToMessage, ApiError } from '@/lib/api';
import { useAppStore } from '@/store/appStore';
import { stripCitationMarkers } from '@/lib/citations';
import type { SearchResponse } from '@/types/api';
import type { UserProfile } from '@/types/agent';
import type { MessageOrigin } from '@/types/chat';

function uid(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

/** Last-resort defensive unwrap. When the LLM returns a JSON envelope in the
 * `answer` field (bug in some fallback paths), extract the inner answer so
 * the chat bubble doesn't show raw JSON to the user. */
function unwrapJsonAnswer(text: string | null | undefined): string {
  if (!text) return '';
  const stripped = text.trim();
  if (!stripped.startsWith('{') || !stripped.endsWith('}')) return text;
  try {
    const parsed = JSON.parse(stripped) as { answer?: unknown };
    if (parsed && typeof parsed.answer === 'string' && parsed.answer.trim()) {
      return parsed.answer.trim();
    }
  } catch {
    // not JSON — leave as-is
  }
  return text;
}

interface SubmitOptions {
  /** Override the profile attached to this request. Falls back to store.lastFinderProfile. */
  profile?: Partial<UserProfile> | null;
  /** Called with the assistant's answer so caller can optionally TTS it. */
  onAnswer?: (payload: SearchResponse) => void;
  /** Whether this turn originated from voice or typed input. Drives compact UI. */
  origin?: MessageOrigin;
}

export function useSearch() {
  const store = useAppStore;

  const submitQuery = useCallback(
    async (rawQuery: string, opts: SubmitOptions = {}): Promise<void> => {
      const query = (rawQuery ?? '').trim();
      const state = store.getState();
      if (!query || state.searchInFlight) return;

      state.setSearchInFlight(true);
      state.setLastQuery(query);
      state.setStatus('Thinking...', 'orange');
      state.setTyping(true);

      state.appendMessage({
        id: uid(),
        role: 'user',
        content: query,
        createdAt: Date.now(),
        origin: opts.origin,
      });

      try {
        const { payload, traceId } = await searchSchemes({
          query,
          user_id: state.sessionUserId || undefined,
          language: state.selectedLanguage,
          profile: opts.profile ?? state.lastFinderProfile ?? null,
          include_plan: true,
        });

        state.setTyping(false);

        if (payload.session_user_id) state.setSessionUserId(payload.session_user_id);
        state.setTrace(traceId, payload.retrieval_debug ?? null);

        if (payload.moderation_blocked) {
          state.appendMessage({
            id: uid(),
            role: 'moderation',
            content: payload.redirect_message ?? 'Please ask about welfare schemes.',
            createdAt: Date.now(),
            moderationCategory: payload.moderation_category,
            payload,
            traceId,
            origin: opts.origin,
          });
          state.setStatus('Ready', 'green');
          return;
        }

        // Defensive: some LLM fallback paths can return a JSON envelope as the answer
        // field. Unwrap so the bubble + TTS speak prose, not machine text.
        const cleanAnswer = unwrapJsonAnswer(payload.answer);
        const normalisedPayload: SearchResponse = cleanAnswer !== payload.answer
          ? { ...payload, answer: cleanAnswer }
          : payload;

        state.appendMessage({
          id: uid(),
          role: 'assistant',
          content: cleanAnswer || 'No answer provided.',
          createdAt: Date.now(),
          payload: normalisedPayload,
          traceId,
          origin: opts.origin,
        });

        const schemes: string[] = [];
        payload.sources.forEach((s) => s.scheme && schemes.push(s.scheme));
        payload.near_miss_sources.forEach((s) => s.scheme && schemes.push(s.scheme));
        if (schemes.length) state.recordSchemes(schemes);

        // Track for the F8 outcome prompt — only the *primary* sources, not the
        // near-misses, so we don't ask "did you apply?" for low-confidence matches.
        const primarySchemes = payload.sources.map((s) => s.scheme).filter(Boolean);
        if (primarySchemes.length) state.recordPendingOutcomes(primarySchemes, traceId);

        if (opts.onAnswer) opts.onAnswer(normalisedPayload);
        else state.setStatus('Ready', 'green');
      } catch (err) {
        state.setTyping(false);
        const { message, code } = mapNetworkErrorToMessage(err);
        state.appendMessage({
          id: uid(),
          role: 'error',
          content: message,
          createdAt: Date.now(),
          origin: opts.origin,
        });
        state.setStatus('Error', 'red');
        window.setTimeout(() => store.getState().setStatus('Ready', 'green'), 3000);
        reportError({
          error: code,
          trace_id: state.lastTraceId,
          language: state.selectedLanguage,
          query_prefix: query.slice(0, 50),
        });
        if (!(err instanceof ApiError)) {
          // eslint-disable-next-line no-console
          console.error('search failure', err);
        }
      } finally {
        store.getState().setSearchInFlight(false);
      }
    },
    [store],
  );

  return {
    submitQuery,
    /** Raw strip helper re-exported for convenience in callers that TTS the answer. */
    stripCitationMarkers,
  };
}
