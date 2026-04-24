import type { SearchResponse } from './api';

export type MessageRole = 'user' | 'assistant' | 'moderation' | 'error';

export type MessageOrigin = 'voice' | 'text';

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: number;
  /** Full backend response payload — attached only to assistant messages. */
  payload?: SearchResponse | null;
  /** Moderation category, present when role === 'moderation'. */
  moderationCategory?: string | null;
  /** Trace id captured from X-Trace-Id response header. */
  traceId?: string | null;
  /** Did the turn start via voice or typed input. Drives compact UI for voice turns. */
  origin?: MessageOrigin;
}
