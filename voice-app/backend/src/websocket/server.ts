import { WebSocketServer as WSServer, WebSocket } from 'ws';
import { v4 as uuidv4 } from 'uuid';
import { logger } from '../utils/logger';
import { Session, WebSocketMessage, WebSocketMessageType } from '../types';
import { WebSocketHandler } from './handlers';

export class WebSocketServer {
  private wss: WSServer | null = null;
  private sessions: Map<string, Session> = new Map();
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private handler: WebSocketHandler;
  private port: number;

  constructor(port: number) {
    this.port = port;
    this.handler = new WebSocketHandler(this.sessions);
  }

  async start(): Promise<void> {
    this.wss = new WSServer({
      port: this.port,
      maxPayload: Number(process.env.WS_MAX_PAYLOAD) || 10 * 1024 * 1024, // 10MB
    });

    this.wss.on('connection', (ws: WebSocket) => {
      this.handleConnection(ws);
    });

    this.wss.on('error', (error) => {
      logger.error('WebSocket server error:', error);
    });

    // Start heartbeat interval
    this.startHeartbeat();

    logger.info(`WebSocket server started on port ${this.port}`);
  }

  async stop(): Promise<void> {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
    }

    // Close all connections
    for (const [sessionId, session] of this.sessions.entries()) {
      session.ws.close(1000, 'Server shutting down');
      this.sessions.delete(sessionId);
    }

    if (this.wss) {
      await new Promise<void>((resolve) => {
        this.wss!.close(() => {
          logger.info('WebSocket server closed');
          resolve();
        });
      });
    }
  }

  private handleConnection(ws: WebSocket): void {
    const sessionId = uuidv4();
    const userId = process.env.MEM0_USER_ID || 'mem0-zai-crew';
    const defaultAgent = (process.env.DEFAULT_VOICE_AGENT as 'elevenlabs' | 'qwen-omni') || 'elevenlabs';

    const session: Session = {
      id: sessionId,
      userId,
      ws,
      audioBuffer: [],
      transcription: '',
      conversationHistory: [],
      voiceAgent: defaultAgent,
      createdAt: new Date(),
      lastActivity: new Date(),
    };

    this.sessions.set(sessionId, session);
    logger.info(`New WebSocket connection: ${sessionId} with voice agent: ${defaultAgent}`);

    // Send welcome message
    this.sendMessage(ws, WebSocketMessageType.STATUS_CHANGE, {
      status: 'idle',
      message: 'Connected to voice assistant',
    });

    ws.on('message', async (data: Buffer) => {
      try {
        const message: WebSocketMessage = JSON.parse(data.toString());
        session.lastActivity = new Date();
        await this.handler.handleMessage(sessionId, message);
      } catch (error) {
        logger.error(`Error handling message from ${sessionId}:`, error);
        this.sendMessage(ws, WebSocketMessageType.ERROR, {
          code: 'INVALID_MESSAGE',
          message: 'Failed to process message',
          details: error instanceof Error ? error.message : String(error),
        });
      }
    });

    ws.on('close', (code, reason) => {
      logger.info(`WebSocket closed: ${sessionId}, code: ${code}, reason: ${reason}`);
      this.sessions.delete(sessionId);
    });

    ws.on('error', (error) => {
      logger.error(`WebSocket error for ${sessionId}:`, error);
      this.sessions.delete(sessionId);
    });

    ws.on('pong', () => {
      session.lastActivity = new Date();
    });
  }

  private sendMessage(ws: WebSocket, type: WebSocketMessageType, payload: unknown): void {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type, payload }));
    }
  }

  private startHeartbeat(): void {
    const interval = Number(process.env.WS_HEARTBEAT_INTERVAL) || 30000;

    this.heartbeatInterval = setInterval(() => {
      const now = Date.now();

      for (const [sessionId, session] of this.sessions.entries()) {
        const timeSinceLastActivity = now - session.lastActivity.getTime();

        // Close stale connections (2x heartbeat interval)
        if (timeSinceLastActivity > interval * 2) {
          logger.warn(`Closing stale connection: ${sessionId}`);
          session.ws.close(1000, 'Connection timeout');
          this.sessions.delete(sessionId);
        } else if (session.ws.readyState === WebSocket.OPEN) {
          // Send ping
          session.ws.ping();
        }
      }
    }, interval);
  }
}
