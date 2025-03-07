import { useState } from 'react';
import { MemoryClient } from 'saket-test';
import { OpenAI } from 'openai';
import { Message, Memory } from '@/types';
import { WELCOME_MESSAGE, INVALID_CONFIG_MESSAGE, ERROR_MESSAGE, AI_MODELS, Provider } from '@/constants/messages';

interface UseChatProps {
  user: string;
  mem0ApiKey: string;
  openaiApiKey: string;
  provider: Provider;
}

interface UseChatReturn {
  messages: Message[];
  memories: Memory[];
  thinking: boolean;
  sendMessage: (content: string, fileData?: { type: string; data: string | Buffer }) => Promise<void>;
}

type MessageContent = string | {
  type: 'image_url';
  image_url: {
    url: string;
  };
};

interface PromptMessage {
  role: string;
  content: MessageContent;
}

export const useChat = ({ user, mem0ApiKey, openaiApiKey, provider }: UseChatProps): UseChatReturn => {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [thinking, setThinking] = useState(false);

  const openai = new OpenAI({ apiKey: openaiApiKey});
  const memoryClient = new MemoryClient({ apiKey: mem0ApiKey });

  const updateMemories = async (messages: PromptMessage[]) => {
    console.log(messages);
    try {
      await memoryClient.add(messages, {
        user_id: user,
        output_format: "v1.1",
      });

      const response = await memoryClient.getAll({
        user_id: user,
        page: 1,
        page_size: 50,
      });

      const newMemories = response.results.map((memory: any) => ({
        id: memory.id,
        content: memory.memory,
        timestamp: memory.updated_at,
        tags: memory.categories || [],
      }));
      setMemories(newMemories);
    } catch (error) {
      console.error('Error in updateMemories:', error);
    }
  };

  const formatMessagesForPrompt = (messages: Message[]): PromptMessage[] => {
    return messages.map((message) => {
      if (message.image) {
        return {
          role: message.sender,
          content: {
            type: 'image_url',
            image_url: {
              url: message.image
            }
          },
        };
      }

      return {
        role: message.sender,
        content: message.content,
      };
    });
  };

  const sendMessage = async (content: string, fileData?: { type: string; data: string | Buffer }) => {
    if (!content.trim() && !fileData) return;

    if (!user) {
      const newMessage: Message = {
        id: Date.now().toString(),
        content,
        sender: 'user',
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, newMessage, INVALID_CONFIG_MESSAGE]);
      return;
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      content,
      sender: 'user',
      timestamp: new Date().toLocaleTimeString(),
      ...(fileData?.type.startsWith('image/') && { image: fileData.data.toString() }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setThinking(true);

    // Get all messages for memory update
    const allMessagesForMemory = formatMessagesForPrompt([...messages, userMessage]);
    await updateMemories(allMessagesForMemory);

    try {
      // Get only the last assistant message (if exists) and the current user message
      const lastAssistantMessage = messages.filter(msg => msg.sender === 'assistant').slice(-1)[0];
      let messagesForLLM = lastAssistantMessage 
        ? [
            formatMessagesForPrompt([lastAssistantMessage])[0],
            formatMessagesForPrompt([userMessage])[0]
          ]
        : [formatMessagesForPrompt([userMessage])[0]];

      // Check if any message has image content
      const hasImage = messagesForLLM.some(msg => {
        if (typeof msg.content === 'object' && msg.content !== null) {
          const content = msg.content as any;
          return content.type === 'image_url';
        }
        return false;
      });

      // For image messages, only use the text content
      if (hasImage) {
        messagesForLLM = [{
          role: 'user',
          content: userMessage.content
        }];
      }

      // Fetch relevant memories if there's an image
      let relevantMemories = '';
      if (hasImage) {
        try {
          const searchResponse = await memoryClient.getAll({
            user_id: user,
            page: 1,
            page_size: 10,
          });

          relevantMemories = searchResponse.results
            .map((memory: any) => `Previous context: ${memory.memory}`)
            .join('\n');
        } catch (error) {
          console.error('Error fetching memories:', error);
        }
      }

      // Add a system message with memories context if there are memories and image
      if (relevantMemories.length > 0 && hasImage) {
        messagesForLLM = [
          {
            role: 'system',
            content: `Here are some relevant details about the user:\n${relevantMemories}\n\nPlease use this context when responding to the user's message.`
          },
          ...messagesForLLM
        ];
      }

      console.log('Messages for LLM:', messagesForLLM);
      const completion = await openai.chat.completions.create({
        model: "gpt-4",
        messages: messagesForLLM.map(msg => ({
          role: msg.role,
          content: msg.content
        })),
        stream: true,
      });

      const assistantMessageId = Date.now() + 1;
      const assistantMessage: Message = {
        id: assistantMessageId.toString(),
        content: '',
        sender: 'assistant',
        timestamp: new Date().toLocaleTimeString(),
      };

      setMessages((prev) => [...prev, assistantMessage]);

      for await (const chunk of completion) {
        const textPart = chunk.choices[0]?.delta?.content || '';
        assistantMessage.content += textPart;
        setThinking(false);

        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId.toString()
              ? { ...msg, content: assistantMessage.content }
              : msg
          )
        );
      }
    } catch (error) {
      console.error('Error in sendMessage:', error);
      setMessages((prev) => [...prev, ERROR_MESSAGE]);
    } finally {
      setThinking(false);
    }
  };

  return {
    messages,
    memories,
    thinking,
    sendMessage,
  };
}; 