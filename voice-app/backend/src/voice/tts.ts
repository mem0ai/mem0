import axios from 'axios';
import { logger } from '../utils/logger';

export class TextToSpeech {
  private apiKey: string;
  private voiceId: string;
  private modelId: string;

  constructor() {
    const apiKey = process.env.ELEVENLABS_API_KEY;
    if (!apiKey) {
      throw new Error('ELEVENLABS_API_KEY environment variable is required');
    }

    this.apiKey = apiKey;
    this.voiceId = process.env.ELEVENLABS_VOICE_ID || 'JBFqnCBsd6RMkjVDRZzb';
    this.modelId = process.env.ELEVENLABS_MODEL_ID || 'eleven_multilingual_v2';
  }

  async synthesize(
    text: string,
    onChunk: (chunk: Buffer, isLast: boolean) => void
  ): Promise<void> {
    try {
      logger.debug(`Synthesizing speech for text: "${text.substring(0, 50)}..."`);

      const response = await axios.post(
        `https://api.elevenlabs.io/v1/text-to-speech/${this.voiceId}/stream`,
        {
          text,
          model_id: this.modelId,
          voice_settings: {
            stability: 0.5,
            similarity_boost: 0.75,
            style: 0.0,
            use_speaker_boost: true,
          },
        },
        {
          headers: {
            'Accept': 'audio/mpeg',
            'Content-Type': 'application/json',
            'xi-api-key': this.apiKey,
          },
          responseType: 'stream',
        }
      );

      const chunks: Buffer[] = [];

      response.data.on('data', (chunk: Buffer) => {
        chunks.push(chunk);
        onChunk(chunk, false);
      });

      await new Promise<void>((resolve, reject) => {
        response.data.on('end', () => {
          logger.debug('TTS streaming completed');
          if (chunks.length > 0) {
            onChunk(Buffer.concat(chunks), true);
          }
          resolve();
        });

        response.data.on('error', (error: Error) => {
          logger.error('TTS streaming error:', error);
          reject(error);
        });
      });
    } catch (error) {
      logger.error('Text-to-speech error:', error);
      throw new Error(
        `Failed to synthesize speech: ${error instanceof Error ? error.message : String(error)}`
      );
    }
  }
}
