import dotenv from 'dotenv';
import { createServer } from 'http';
import express from 'express';
import { WebSocketServer } from './websocket/server';
import { logger } from './utils/logger';

// Load environment variables
dotenv.config();

const PORT = process.env.PORT || 3001;
const WS_PORT = process.env.WS_PORT || 8080;

async function main() {
  try {
    // Create HTTP server for health checks and API endpoints
    const app = express();
    app.use(express.json());

    // Health check endpoint
    app.get('/health', (req, res) => {
      res.json({ status: 'ok', timestamp: new Date().toISOString() });
    });

    const httpServer = createServer(app);

    // Start WebSocket server
    const wsServer = new WebSocketServer(Number(WS_PORT));
    await wsServer.start();

    // Start HTTP server
    httpServer.listen(PORT, () => {
      logger.info(`HTTP server listening on port ${PORT}`);
      logger.info(`WebSocket server listening on port ${WS_PORT}`);
      logger.info('Voice application backend started successfully');
    });

    // Graceful shutdown
    process.on('SIGTERM', async () => {
      logger.info('SIGTERM signal received: closing servers');
      await wsServer.stop();
      httpServer.close(() => {
        logger.info('HTTP server closed');
        process.exit(0);
      });
    });

    process.on('SIGINT', async () => {
      logger.info('SIGINT signal received: closing servers');
      await wsServer.stop();
      httpServer.close(() => {
        logger.info('HTTP server closed');
        process.exit(0);
      });
    });
  } catch (error) {
    logger.error('Failed to start server:', error);
    process.exit(1);
  }
}

main();
