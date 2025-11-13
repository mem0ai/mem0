import { ChatMessage } from '@/lib/types';
import { cn } from '@/lib/utils';

interface ChatBubbleProps {
  message: ChatMessage;
}

export function ChatBubble({ message }: ChatBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <div
      className={cn(
        'flex w-full mb-4 animate-fadeIn',
        isUser ? 'justify-start' : 'justify-end'
      )}
    >
      <div
        className={cn(
          'max-w-[70%] rounded-2xl px-4 py-3 shadow-lg',
          isUser
            ? 'bg-blue-100 text-blue-900 rounded-bl-none'
            : 'bg-pink-100 text-pink-900 rounded-br-none'
        )}
      >
        <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
        <span className="text-xs opacity-60 mt-1 block">
          {message.timestamp.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </span>
      </div>
    </div>
  );
}
