import WebSocket from 'ws';
import { logger } from '../utils/logger';
import { EventEmitter } from 'events';

interface QWenOmniConfig {
  apiKey: string;
  model?: string;
  voice?: string;
  endpoint?: string;
}

interface QWenMessage {
  type: string;
  [key: string]: unknown;
}

/**
 * QWen 3 Omni Real-time Voice Provider
 * Supports real-time speech recognition, LLM processing, and emotional TTS
 */
export class QWenOmniProvider extends EventEmitter {
  private apiKey: string;
  private model: string;
  private voice: string;
  private endpoint: string;
  private ws: WebSocket | null = null;
  private isConnected = false;
  private sessionId: string | null = null;
  private audioQueue: Buffer[] = [];

  constructor(config?: Partial<QWenOmniConfig>) {
    super();

    const apiKey = config?.apiKey || process.env.DASHSCOPE_API_KEY;
    if (!apiKey) {
      throw new Error('DASHSCOPE_API_KEY environment variable is required');
    }

    this.apiKey = apiKey;
    this.model = config?.model || process.env.QWEN_OMNI_MODEL || 'qwen3-omni-flash-realtime';
    this.voice = config?.voice || process.env.QWEN_OMNI_VOICE || 'Cherry';
    this.endpoint = config?.endpoint || process.env.QWEN_OMNI_ENDPOINT || 'wss://dashscope.aliyuncs.com/api-ws/v1/realtime';
  }

  /**
   * Connect to QWen Omni real-time API
   */
  async connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        const url = `${this.endpoint}?model=${this.model}`;

        logger.info(`Connecting to QWen Omni: ${url}`);

        this.ws = new WebSocket(url, {
          headers: {
            'Authorization': `Bearer ${this.apiKey}`,
          },
        });

        this.ws.on('open', () => {
          logger.info('QWen Omni WebSocket connected');
          this.isConnected = true;

          // Configure session
          this.configureSession();

          resolve();
        });

        this.ws.on('message', (data: Buffer) => {
          this.handleMessage(data);
        });

        this.ws.on('error', (error) => {
          logger.error('QWen Omni WebSocket error:', error);
          this.emit('error', error);
          reject(error);
        });

        this.ws.on('close', () => {
          logger.info('QWen Omni WebSocket closed');
          this.isConnected = false;
          this.emit('disconnected');
        });

      } catch (error) {
        logger.error('Failed to connect to QWen Omni:', error);
        reject(error);
      }
    });
  }

  /**
   * Configure the session with voice and audio settings
   */
  private configureSession(): void {
    if (!this.ws || !this.isConnected) {
      throw new Error('WebSocket not connected');
    }

    const config = {
      type: 'session.update',
      session: {
        modalities: ['text', 'audio'],
        voice: this.voice,
        input_audio_format: 'pcm16',
        output_audio_format: 'pcm16',
        turn_detection: null, // Manual mode
        instructions: 'You are a helpful AI assistant with emotional voice capabilities. Respond naturally and expressively.',
      },
    };

    logger.debug('Configuring QWen Omni session:', config);
    this.ws.send(JSON.stringify(config));
  }

  /**
   * Handle incoming messages from QWen Omni
   */
  private handleMessage(data: Buffer): void {
    try {
      const message: QWenMessage = JSON.parse(data.toString());

      logger.debug(`QWen message type: ${message.type}`);

      switch (message.type) {
        case 'session.created':
          this.sessionId = (message as any).session?.id;
          logger.info(`QWen session created: ${this.sessionId}`);
          this.emit('session_ready');
          break;

        case 'session.updated':
          logger.debug('QWen session updated');
          break;

        case 'input_audio_buffer.speech_started':
          logger.debug('User started speaking');
          this.emit('speech_started');
          break;

        case 'input_audio_buffer.speech_stopped':
          logger.debug('User stopped speaking');
          this.emit('speech_stopped');
          break;

        case 'conversation.item.input_audio_transcription.completed':
          const transcription = (message as any).transcript || '';
          logger.debug(`Transcription: ${transcription}`);
          this.emit('transcription', transcription, true);
          break;

        case 'conversation.item.input_audio_transcription.delta':
          const partialTranscript = (message as any).delta || '';
          this.emit('transcription', partialTranscript, false);
          break;

        case 'response.audio.delta':
          // Streaming audio from AI
          const audioData = (message as any).delta;
          if (audioData) {
            const audioBuffer = Buffer.from(audioData, 'base64');
            this.emit('audio_chunk', audioBuffer);
          }
          break;

        case 'response.audio_transcript.delta':
          // Streaming text transcript of AI response
          const textDelta = (message as any).delta || '';
          this.emit('response_text', textDelta);
          break;

        case 'response.audio_transcript.done':
          const fullText = (message as any).transcript || '';
          this.emit('response_text_complete', fullText);
          break;

        case 'response.done':
          logger.debug('Response completed');
          this.emit('response_complete');
          break;

        case 'error':
          const errorMsg = (message as any).error?.message || 'Unknown error';
          logger.error(`QWen error: ${errorMsg}`);
          this.emit('error', new Error(errorMsg));
          break;

        default:
          logger.debug(`Unhandled QWen message type: ${message.type}`);
      }
    } catch (error) {
      logger.error('Error parsing QWen message:', error);
    }
  }

  /**
   * Send audio chunk to QWen for processing
   */
  sendAudioChunk(audioData: Buffer): void {
    if (!this.ws || !this.isConnected) {
      logger.warn('Cannot send audio: WebSocket not connected');
      return;
    }

    const base64Audio = audioData.toString('base64');

    const message = {
      type: 'input_audio_buffer.append',
      audio: base64Audio,
    };

    this.ws.send(JSON.stringify(message));
  }

  /**
   * Commit audio buffer and trigger response
   */
  commitAudio(): void {
    if (!this.ws || !this.isConnected) {
      logger.warn('Cannot commit audio: WebSocket not connected');
      return;
    }

    // First commit the audio buffer
    this.ws.send(JSON.stringify({
      type: 'input_audio_buffer.commit',
    }));

    // Then create a response
    setTimeout(() => {
      this.ws!.send(JSON.stringify({
        type: 'response.create',
        response: {
          modalities: ['text', 'audio'],
        },
      }));
    }, 100);
  }

  /**
   * Cancel current response
   */
  cancelResponse(): void {
    if (!this.ws || !this.isConnected) {
      return;
    }

    this.ws.send(JSON.stringify({
      type: 'response.cancel',
    }));
  }

  /**
   * Clear audio buffer
   */
  clearAudioBuffer(): void {
    if (!this.ws || !this.isConnected) {
      return;
    }

    this.ws.send(JSON.stringify({
      type: 'input_audio_buffer.clear',
    }));
  }

  /**
   * Disconnect from QWen Omni
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
      this.isConnected = false;
      this.sessionId = null;
    }
  }

  /**
   * Check if connected
   */
  get connected(): boolean {
    return this.isConnected;
  }
}
