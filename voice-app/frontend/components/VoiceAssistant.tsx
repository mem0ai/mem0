'use client';

import { useState, useCallback } from 'react';
import { AnimatedOrb } from './AnimatedOrb';
import { ChatUI } from './ChatUI';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useAudioRecorder, useAudioPlayer } from '@/hooks/useAudio';
import { ChatMessage, AssistantStatus } from '@/lib/types';
import { Mic, MicOff } from 'lucide-react';
import { cn } from '@/lib/utils';

export function VoiceAssistant() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [currentTranscription, setCurrentTranscription] = useState('');
  const [currentAIResponse, setCurrentAIResponse] = useState('');
  const [status, setStatus] = useState<AssistantStatus>('idle');

  const { playAudio } = useAudioPlayer();

  // WebSocket connection
  const { isConnected, sendAudioChunk, startRecording: wsStartRecording, stopRecording: wsStopRecording } = useWebSocket({
    url: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8080',
    onTranscriptionUpdate: (text, isFinal) => {
      if (isFinal) {
        setMessages((prev) => [
          ...prev,
          {
            id: `msg-${Date.now()}`,
            role: 'user',
            content: text,
            timestamp: new Date(),
          },
        ]);
        setCurrentTranscription('');
      } else {
        setCurrentTranscription(text);
      }
    },
    onAIResponseText: (text) => {
      setCurrentAIResponse(text);
    },
    onAIResponseAudio: (audio, messageId, isLast) => {
      playAudio(audio);

      if (isLast) {
        setMessages((prev) => [
          ...prev,
          {
            id: messageId,
            role: 'assistant',
            content: currentAIResponse,
            timestamp: new Date(),
          },
        ]);
        setCurrentAIResponse('');
      }
    },
    onStatusChange: (newStatus) => {
      setStatus(newStatus);
    },
    onError: (error) => {
      console.error('WebSocket error:', error);
    },
  });

  // Audio recording
  const { isRecording, startRecording, stopRecording } = useAudioRecorder();

  const handleMouseDown = useCallback(async () => {
    try {
      wsStartRecording();
      await startRecording((audioData) => {
        sendAudioChunk(audioData, 16000);
      });
    } catch (error) {
      console.error('Failed to start recording:', error);
    }
  }, [startRecording, sendAudioChunk, wsStartRecording]);

  const handleMouseUp = useCallback(() => {
    stopRecording();
    wsStopRecording();
  }, [stopRecording, wsStopRecording]);

  const getStatusText = () => {
    switch (status) {
      case 'listening':
        return 'Listening...';
      case 'processing':
        return 'Processing...';
      case 'speaking':
        return 'Speaking...';
      default:
        return isConnected ? 'Ready' : 'Connecting...';
    }
  };

  const getStatusColor = () => {
    switch (status) {
      case 'listening':
        return 'text-blue-400';
      case 'processing':
        return 'text-yellow-400';
      case 'speaking':
        return 'text-pink-400';
      default:
        return isConnected ? 'text-green-400' : 'text-gray-400';
    }
  };

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 px-6 py-3 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">AI Voice Assistant</h1>
          <p className={cn('text-sm', getStatusColor())}>{getStatusText()}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className={cn(
            'w-3 h-3 rounded-full',
            isConnected ? 'bg-green-500 animate-pulse' : 'bg-gray-500'
          )} />
          <span className="text-sm text-gray-400">
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex">
        {/* Animated Orb - Left side */}
        <div className="w-1/2 flex flex-col items-center justify-center bg-gradient-to-br from-gray-900 via-black to-gray-900 p-8">
          <div className="w-full h-96 mb-8">
            <AnimatedOrb
              userSpeaking={status === 'listening' || isRecording}
              aiSpeaking={status === 'speaking'}
            />
          </div>

          {/* Voice button */}
          <button
            onMouseDown={handleMouseDown}
            onMouseUp={handleMouseUp}
            onTouchStart={handleMouseDown}
            onTouchEnd={handleMouseUp}
            disabled={!isConnected || status === 'processing' || status === 'speaking'}
            className={cn(
              'relative group p-8 rounded-full transition-all duration-200',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              isRecording
                ? 'bg-blue-500 shadow-lg shadow-blue-500/50 scale-110'
                : 'bg-gray-700 hover:bg-gray-600 hover:shadow-lg'
            )}
          >
            {isRecording ? (
              <Mic className="w-12 h-12 text-white" />
            ) : (
              <MicOff className="w-12 h-12 text-gray-300" />
            )}

            <div className="absolute -bottom-12 left-1/2 -translate-x-1/2 whitespace-nowrap text-sm text-gray-400">
              {isRecording ? 'Release to send' : 'Hold to speak'}
            </div>
          </button>
        </div>

        {/* Chat UI - Right side */}
        <div className="w-1/2 border-l border-gray-700">
          <ChatUI messages={messages} currentTranscription={currentTranscription} />
        </div>
      </div>
    </div>
  );
}
