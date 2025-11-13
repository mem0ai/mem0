import { logger } from '../utils/logger';
import { Message } from '../types';
import { SpeechToText } from './stt';
import { TextToSpeech } from './tts';
import { ClaudeClient } from '../llm/claude';
import { v4 as uuidv4 } from 'uuid';

export interface VoicePipelineInput {
  audioData: Buffer;
  userId: string;
  conversationHistory: Message[];
  onTranscriptionUpdate?: (text: string, isFinal: boolean) => void;
  onResponseText?: (text: string, messageId: string) => void;
  onResponseAudio?: (audio: Buffer, messageId: string, isLast: boolean) => void;
}

export interface VoicePipelineOutput {
  transcription: string;
  response: string;
  audioResponse?: Buffer;
}

export class VoicePipeline {
  private stt: SpeechToText;
  private tts: TextToSpeech;
  private claude: ClaudeClient;

  constructor() {
    this.stt = new SpeechToText();
    this.tts = new TextToSpeech();
    this.claude = new ClaudeClient();
  }

  async process(input: VoicePipelineInput): Promise<VoicePipelineOutput> {
    const messageId = uuidv4();

    try {
      // Step 1: Speech to Text
      logger.info('Step 1: Converting speech to text');
      const transcription = await this.stt.transcribe(input.audioData);

      if (input.onTranscriptionUpdate) {
        input.onTranscriptionUpdate(transcription, true);
      }

      logger.info(`Transcription: "${transcription}"`);

      // Step 2: Process with Claude + MCP tools
      logger.info('Step 2: Processing with Claude and MCP tools');
      const response = await this.claude.chat({
        userId: input.userId,
        message: transcription,
        conversationHistory: input.conversationHistory,
        onTextChunk: input.onResponseText
          ? (text) => input.onResponseText!(text, messageId)
          : undefined,
      });

      logger.info(`Claude response: "${response}"`);

      // Step 3: Text to Speech
      logger.info('Step 3: Converting response to speech');
      const audioChunks: Buffer[] = [];

      await this.tts.synthesize(response, (chunk, isLast) => {
        audioChunks.push(chunk);
        if (input.onResponseAudio) {
          input.onResponseAudio(chunk, messageId, isLast);
        }
      });

      const fullAudio = Buffer.concat(audioChunks);

      return {
        transcription,
        response,
        audioResponse: fullAudio,
      };
    } catch (error) {
      logger.error('Voice pipeline error:', error);
      throw error;
    }
  }
}
