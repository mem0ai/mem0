import { WebSocket } from 'ws';
import { logger } from '../utils/logger';
import {
  Session,
  WebSocketMessage,
  WebSocketMessageType,
  AudioChunkPayload,
} from '../types';
import { VoicePipeline } from '../voice/pipeline';

export class WebSocketHandler {
  private sessions: Map<string, Session>;
  private voicePipeline: VoicePipeline;

  constructor(sessions: Map<string, Session>) {
    this.sessions = sessions;
    this.voicePipeline = new VoicePipeline();
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

      logger.info(`Processing audio: ${audioData.length} bytes`);

      // Process through voice pipeline
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

  private sendMessage(ws: WebSocket, type: WebSocketMessageType, payload: unknown): void {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type, payload }));
    }
  }
}
