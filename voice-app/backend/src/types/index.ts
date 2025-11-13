import type { WebSocket } from 'ws';

export interface Session {
  id: string;
  userId: string;
  ws: WebSocket;
  audioBuffer: Buffer[];
  transcription: string;
  conversationHistory: Message[];
  createdAt: Date;
  lastActivity: Date;
}

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  audio?: string; // Base64 encoded audio
}

export interface WebSocketMessage {
  type: WebSocketMessageType;
  payload: unknown;
}

export enum WebSocketMessageType {
  // Client -> Server
  AUDIO_CHUNK = 'audio_chunk',
  START_RECORDING = 'start_recording',
  STOP_RECORDING = 'stop_recording',

  // Server -> Client
  TRANSCRIPTION_UPDATE = 'transcription_update',
  AI_RESPONSE_TEXT = 'ai_response_text',
  AI_RESPONSE_AUDIO = 'ai_response_audio',
  STATUS_CHANGE = 'status_change',
  ERROR = 'error',

  // Bidirectional
  PING = 'ping',
  PONG = 'pong',
}

export interface AudioChunkPayload {
  audio: string; // Base64 encoded audio chunk
  sampleRate: number;
  channels: number;
}

export interface TranscriptionUpdatePayload {
  text: string;
  isFinal: boolean;
}

export interface AIResponseTextPayload {
  text: string;
  messageId: string;
}

export interface AIResponseAudioPayload {
  audio: string; // Base64 encoded audio chunk
  messageId: string;
  isLast: boolean;
}

export interface StatusChangePayload {
  status: 'listening' | 'processing' | 'speaking' | 'idle';
  message?: string;
}

export interface ErrorPayload {
  code: string;
  message: string;
  details?: unknown;
}

export interface VoicePipelineConfig {
  sttProvider: 'whisper' | 'deepgram';
  ttsProvider: 'elevenlabs' | 'openai';
  llmProvider: 'claude';
}

export interface MCPServerConfig {
  name: string;
  command: string;
  args: string[];
  env?: Record<string, string>;
}
