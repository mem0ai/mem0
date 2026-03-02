import OpenAI from 'openai';
import { logger } from '../utils/logger';
import { writeFileSync, unlinkSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

export class SpeechToText {
  private client: OpenAI;
  private model: string;

  constructor() {
    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey) {
      throw new Error('OPENAI_API_KEY environment variable is required');
    }

    this.client = new OpenAI({ apiKey });
    this.model = process.env.WHISPER_MODEL || 'whisper-1';
  }

  async transcribe(audioData: Buffer): Promise<string> {
    let tempFilePath: string | null = null;

    try {
      // Write audio to temporary file
      // Whisper API requires a file input
      tempFilePath = join(tmpdir(), `audio-${Date.now()}.webm`);
      writeFileSync(tempFilePath, audioData);

      logger.debug(`Transcribing audio file: ${tempFilePath}`);

      const transcription = await this.client.audio.transcriptions.create({
        file: await import('fs').then((fs) => fs.createReadStream(tempFilePath!)),
        model: this.model,
        language: 'en', // Can be made configurable
        response_format: 'text',
      });

      const text = typeof transcription === 'string' ? transcription : transcription.text;

      return text.trim();
    } catch (error) {
      logger.error('Speech-to-text error:', error);
      throw new Error(
        `Failed to transcribe audio: ${error instanceof Error ? error.message : String(error)}`
      );
    } finally {
      // Clean up temporary file
      if (tempFilePath) {
        try {
          unlinkSync(tempFilePath);
        } catch (err) {
          logger.warn(`Failed to delete temp file: ${tempFilePath}`, err);
        }
      }
    }
  }
}
