import { useEffect, useRef } from 'react';
import { ChatMessage } from '@/lib/types';
import { ChatBubble } from './ChatBubble';

interface ChatUIProps {
  messages: ChatMessage[];
  currentTranscription?: string;
}

export function ChatUI({ messages, currentTranscription }: ChatUIProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Auto-scroll to bottom when new messages arrive
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, currentTranscription]);

  return (
    <div className="flex flex-col h-full">
      <div className="bg-gray-800 px-6 py-4 border-b border-gray-700">
        <h2 className="text-xl font-semibold text-white">Voice Assistant</h2>
        <p className="text-sm text-gray-400">Powered by Claude, mem0, and Eleven Labs</p>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-6 py-4 space-y-4 bg-gray-900"
      >
        {messages.map((message) => (
          <ChatBubble key={message.id} message={message} />
        ))}

        {currentTranscription && (
          <div className="flex justify-start mb-4 opacity-70">
            <div className="max-w-[70%] rounded-2xl px-4 py-3 bg-blue-50 text-blue-900 rounded-bl-none border-2 border-blue-300 border-dashed">
              <p className="text-sm leading-relaxed">{currentTranscription}</p>
              <span className="text-xs text-blue-600 mt-1 block">
                Listening...
              </span>
            </div>
          </div>
        )}

        {messages.length === 0 && !currentTranscription && (
          <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
              <p className="text-lg mb-2">No messages yet</p>
              <p className="text-sm">Press and hold the button to start speaking</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
