import { useEffect, useRef, useCallback, useState } from 'react';
import {
  WebSocketMessage,
  WebSocketMessageType,
  TranscriptionUpdatePayload,
  AIResponseTextPayload,
  AIResponseAudioPayload,
  StatusChangePayload,
  ErrorPayload,
  AssistantStatus,
  VoiceAgent,
  VoiceAgentChangedPayload,
} from '@/lib/types';

interface UseWebSocketOptions {
  url: string;
  onTranscriptionUpdate?: (text: string, isFinal: boolean) => void;
  onAIResponseText?: (text: string, messageId: string) => void;
  onAIResponseAudio?: (audio: string, messageId: string, isLast: boolean) => void;
  onStatusChange?: (status: AssistantStatus, message?: string) => void;
  onError?: (error: ErrorPayload) => void;
  onVoiceAgentChanged?: (agent: VoiceAgent) => void;
}

export function useWebSocket(options: UseWebSocketOptions) {
  const [isConnected, setIsConnected] = useState(false);
  const [status, setStatus] = useState<AssistantStatus>('idle');
  const [currentAgent, setCurrentAgent] = useState<VoiceAgent>('elevenlabs');
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const audioQueueRef = useRef<AudioBuffer[]>([]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    const ws = new WebSocket(options.url);

    ws.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
      setStatus('idle');
    };

    ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);

        switch (message.type) {
          case WebSocketMessageType.TRANSCRIPTION_UPDATE: {
            const payload = message.payload as TranscriptionUpdatePayload;
            options.onTranscriptionUpdate?.(payload.text, payload.isFinal);
            break;
          }

          case WebSocketMessageType.AI_RESPONSE_TEXT: {
            const payload = message.payload as AIResponseTextPayload;
            options.onAIResponseText?.(payload.text, payload.messageId);
            break;
          }

          case WebSocketMessageType.AI_RESPONSE_AUDIO: {
            const payload = message.payload as AIResponseAudioPayload;
            options.onAIResponseAudio?.(payload.audio, payload.messageId, payload.isLast);
            break;
          }

          case WebSocketMessageType.STATUS_CHANGE: {
            const payload = message.payload as StatusChangePayload;
            setStatus(payload.status);
            options.onStatusChange?.(payload.status, payload.message);
            break;
          }

          case WebSocketMessageType.ERROR: {
            const payload = message.payload as ErrorPayload;
            console.error('WebSocket error:', payload);
            options.onError?.(payload);
            break;
          }

          case WebSocketMessageType.VOICE_AGENT_CHANGED: {
            const payload = message.payload as VoiceAgentChangedPayload;
            setCurrentAgent(payload.agent);
            options.onVoiceAgentChanged?.(payload.agent);
            break;
          }

          case WebSocketMessageType.PING:
            sendMessage(WebSocketMessageType.PONG, {});
            break;
        }
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
      setStatus('idle');

      // Attempt reconnection after 3 seconds
      reconnectTimeoutRef.current = setTimeout(() => {
        console.log('Attempting to reconnect...');
        connect();
      }, 3000);
    };

    wsRef.current = ws;
  }, [options]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  const sendMessage = useCallback((type: WebSocketMessageType, payload: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, payload }));
    } else {
      console.warn('WebSocket not connected, cannot send message');
    }
  }, []);

  const sendAudioChunk = useCallback((audioData: ArrayBuffer, sampleRate: number) => {
    const base64 = arrayBufferToBase64(audioData);
    sendMessage(WebSocketMessageType.AUDIO_CHUNK, {
      audio: base64,
      sampleRate,
      channels: 1,
    });
  }, [sendMessage]);

  const startRecording = useCallback(() => {
    sendMessage(WebSocketMessageType.START_RECORDING, {});
  }, [sendMessage]);

  const stopRecording = useCallback(() => {
    sendMessage(WebSocketMessageType.STOP_RECORDING, {});
  }, [sendMessage]);

  const setVoiceAgent = useCallback((agent: VoiceAgent) => {
    sendMessage(WebSocketMessageType.SET_VOICE_AGENT, { agent });
  }, [sendMessage]);

  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    isConnected,
    status,
    currentAgent,
    sendAudioChunk,
    startRecording,
    stopRecording,
    setVoiceAgent,
  };
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}
