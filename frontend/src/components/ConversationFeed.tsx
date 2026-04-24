import { useEffect, useRef } from 'react';
import { useAppStore } from '@/store/appStore';
import { AssistantMessage } from './messages/AssistantMessage';
import { UserMessage } from './messages/UserMessage';
import { ModerationMessage } from './messages/ModerationMessage';
import { ErrorMessage } from './messages/ErrorMessage';
import { TypingIndicator } from './TypingIndicator';

export function ConversationFeed() {
  const messages = useAppStore((s) => s.messages);
  const typing = useAppStore((s) => s.typing);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length, typing]);

  if (!messages.length && !typing) return null;

  return (
    <div className="flex flex-col gap-4" role="log" aria-live="polite" aria-label="Conversation">
      {messages.map((m) => {
        if (m.role === 'user') return <UserMessage key={m.id} content={m.content} />;
        if (m.role === 'moderation')
          return <ModerationMessage key={m.id} content={m.content} category={m.moderationCategory} />;
        if (m.role === 'error') return <ErrorMessage key={m.id} content={m.content} />;
        if (m.role === 'assistant' && m.payload) {
          return (
            <AssistantMessage
              key={m.id}
              payload={m.payload}
              content={m.content}
              compact={m.origin === 'voice'}
            />
          );
        }
        return null;
      })}
      {typing && <TypingIndicator />}
      <div ref={bottomRef} />
    </div>
  );
}
