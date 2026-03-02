import { WebSocket } from 'ws';
import { logger } from '../utils/logger';
import {
  Session,
  WebSocketMessage,
  WebSocketMessageType,
  AudioChunkPayload,
  SetVoiceAgentPayload,
  VoiceAgent,
} from '../types';
import { VoicePipeline } from '../voice/pipeline';
import { QWenOmniProvider } from '../voice/qwen-omni';

export class WebSocketHandler {
  private sessions: Map<string, Session>;
  private voicePipeline: VoicePipeline;
  private qwenProviders: Map<string, QWenOmniProvider>;

  constructor(sessions: Map<string, Session>) {
    this.sessions = sessions;
    this.voicePipeline = new VoicePipeline();
    this.qwenProviders = new Map();
  }

  async handleMessage(sessionId: string, message: WebSocketMessage): Promise<void> {
    const session = this.sessions.get(sessionId);
    if (!session) {
      logger.warn(`Session not found: ${sessionId}`);
      return;
    }

    logger.debug(`Handling message type: ${message.type} for session: ${sessionId}`);

    switch (message.type) {
      case WebSocketMessageType.AUDIO_CHUNK:
        await this.handleAudioChunk(session, message.payload as AudioChunkPayload);
        break;

      case WebSocketMessageType.START_RECORDING:
        await this.handleStartRecording(session);
        break;

      case WebSocketMessageType.STOP_RECORDING:
        await this.handleStopRecording(session);
        break;

      case WebSocketMessageType.SET_VOICE_AGENT:
        await this.handleSetVoiceAgent(session, message.payload as SetVoiceAgentPayload);
        break;

      case WebSocketMessageType.PONG:
        // Heartbeat handled in server
        break;

      default:
        logger.warn(`Unknown message type: ${message.type}`);
        this.sendMessage(session.ws, WebSocketMessageType.ERROR, {
          code: 'UNKNOWN_MESSAGE_TYPE',
          message: `Unknown message type: ${message.type}`,
        });
    }
  }

  private async handleAudioChunk(session: Session, payload: AudioChunkPayload): Promise<void> {
    try {
      // Decode base64 audio chunk
      const audioBuffer = Buffer.from(payload.audio, 'base64');
      session.audioBuffer.push(audioBuffer);

      logger.debug(`Received audio chunk: ${audioBuffer.length} bytes`);
    } catch (error) {
      logger.error('Error handling audio chunk:', error);
      this.sendMessage(session.ws, WebSocketMessageType.ERROR, {
        code: 'AUDIO_PROCESSING_ERROR',
        message: 'Failed to process audio chunk',
      });
    }
  }

  private async handleStartRecording(session: Session): Promise<void> {
    logger.info(`Starting recording for session: ${session.id}`);
    session.audioBuffer = [];
    session.transcription = '';

    this.sendMessage(session.ws, WebSocketMessageType.STATUS_CHANGE, {
      status: 'listening',
      message: 'Listening...',
    });
  }

  private async handleSetVoiceAgent(session: Session, payload: SetVoiceAgentPayload): Promise<void> {
    const { agent } = payload;
    logger.info(`Switching voice agent to: ${agent} for session: ${session.id}`);

    try {
      // Clean up old QWen provider if switching away
      if (session.voiceAgent === 'qwen-omni') {
        const qwenProvider = this.qwenProviders.get(session.id);
        if (qwenProvider) {
          qwenProvider.disconnect();
          this.qwenProviders.delete(session.id);
        }
      }

      // Initialize new QWen provider if switching to it
      if (agent === 'qwen-omni') {
        const qwenProvider = new QWenOmniProvider();
        await qwenProvider.connect();
        this.qwenProviders.set(session.id, qwenProvider);
      }

      session.voiceAgent = agent;

      this.sendMessage(session.ws, WebSocketMessageType.VOICE_AGENT_CHANGED, {
        agent,
      });

      logger.info(`Voice agent switched successfully to: ${agent}`);
    } catch (error) {
      logger.error(`Error switching voice agent:`, error);
      this.sendMessage(session.ws, WebSocketMessageType.ERROR, {
        code: 'AGENT_SWITCH_ERROR',
        message: `Failed to switch to ${agent}`,
        details: error instanceof Error ? error.message : String(error),
      });
    }
  }

  private async handleStopRecording(session: Session): Promise<void> {
    logger.info(`Stopping recording for session: ${session.id}`);

    this.sendMessage(session.ws, WebSocketMessageType.STATUS_CHANGE, {
      status: 'processing',
      message: 'Processing your message...',
    });

    try {
      // Combine audio buffers
      const audioData = Buffer.concat(session.audioBuffer);

      if (audioData.length === 0) {
        logger.warn('No audio data received');
        this.sendMessage(session.ws, WebSocketMessageType.ERROR, {
          code: 'NO_AUDIO_DATA',
          message: 'No audio data received',
        });
        this.sendMessage(session.ws, WebSocketMessageType.STATUS_CHANGE, {
          status: 'idle',
        });
        return;
      }

      logger.info(`Processing audio: ${audioData.length} bytes using ${session.voiceAgent}`);

      // Route to appropriate voice agent
      if (session.voiceAgent === 'qwen-omni') {
        await this.processWithQWenOmni(session, audioData);
      } else {
        await this.processWithElevenLabs(session, audioData);
      }

      // Clear audio buffer
      session.audioBuffer = [];

      this.sendMessage(session.ws, WebSocketMessageType.STATUS_CHANGE, {
        status: 'idle',
        message: 'Ready for next message',
      });
    } catch (error) {
      logger.error('Error processing audio:', error);
      this.sendMessage(session.ws, WebSocketMessageType.ERROR, {
        code: 'PROCESSING_ERROR',
        message: 'Failed to process audio',
        details: error instanceof Error ? error.message : String(error),
      });
      this.sendMessage(session.ws, WebSocketMessageType.STATUS_CHANGE, {
        status: 'idle',
      });
    }
  }

  private async processWithElevenLabs(session: Session, audioData: Buffer): Promise<void> {
    // Process through voice pipeline (Whisper STT + Claude + ElevenLabs TTS)
    const result = await this.voicePipeline.process({
      audioData,
      userId: session.userId,
      conversationHistory: session.conversationHistory,
      onTranscriptionUpdate: (text, isFinal) => {
        this.sendMessage(session.ws, WebSocketMessageType.TRANSCRIPTION_UPDATE, {
          text,
          isFinal,
        });
        if (isFinal) {
          session.transcription = text;
        }
      },
      onResponseText: (text, messageId) => {
        this.sendMessage(session.ws, WebSocketMessageType.AI_RESPONSE_TEXT, {
          text,
          messageId,
        });
      },
      onResponseAudio: (audio, messageId, isLast) => {
        this.sendMessage(session.ws, WebSocketMessageType.AI_RESPONSE_AUDIO, {
          audio: audio.toString('base64'),
          messageId,
          isLast,
        });
      },
    });

    // Update conversation history
    session.conversationHistory.push(
      {
        role: 'user',
        content: result.transcription,
        timestamp: new Date(),
      },
      {
        role: 'assistant',
        content: result.response,
        timestamp: new Date(),
      }
    );
  }

  private async processWithQWenOmni(session: Session, audioData: Buffer): Promise<void> {
    const qwenProvider = this.qwenProviders.get(session.id);
    if (!qwenProvider) {
      throw new Error('QWen Omni provider not initialized');
    }

    const messageId = require('uuid').v4();
    let fullTranscription = '';
    let fullResponse = '';

    // Set up event listeners
    qwenProvider.once('transcription', (text: string, isFinal: boolean) => {
      if (isFinal) {
        fullTranscription = text;
        this.sendMessage(session.ws, WebSocketMessageType.TRANSCRIPTION_UPDATE, {
          text,
          isFinal: true,
        });
        session.transcription = text;
      }
    });

    qwenProvider.on('response_text', (text: string) => {
      fullResponse += text;
      this.sendMessage(session.ws, WebSocketMessageType.AI_RESPONSE_TEXT, {
        text: fullResponse,
        messageId,
      });
    });

    qwenProvider.on('audio_chunk', (audioChunk: Buffer) => {
      this.sendMessage(session.ws, WebSocketMessageType.AI_RESPONSE_AUDIO, {
        audio: audioChunk.toString('base64'),
        messageId,
        isLast: false,
      });
    });

    qwenProvider.once('response_complete', () => {
      this.sendMessage(session.ws, WebSocketMessageType.AI_RESPONSE_AUDIO, {
        audio: '',
        messageId,
        isLast: true,
      });

      // Update conversation history
      session.conversationHistory.push(
        {
          role: 'user',
          content: fullTranscription,
          timestamp: new Date(),
        },
        {
          role: 'assistant',
          content: fullResponse,
          timestamp: new Date(),
        }
      );
    });

    // Send audio data
    // QWen expects PCM16 audio in chunks
    const chunkSize = 4096;
    for (let i = 0; i < audioData.length; i += chunkSize) {
      const chunk = audioData.slice(i, Math.min(i + chunkSize, audioData.length));
      qwenProvider.sendAudioChunk(chunk);
      // Small delay to avoid overwhelming the API
      await new Promise(resolve => setTimeout(resolve, 10));
    }

    // Commit audio and trigger response
    qwenProvider.commitAudio();
  }

  private sendMessage(ws: WebSocket, type: WebSocketMessageType, payload: unknown): void {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type, payload }));
    }
  }
}
