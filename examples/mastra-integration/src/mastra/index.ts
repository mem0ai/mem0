
import { Mastra } from '@mastra/core/mastra';
import { createLogger } from '@mastra/core/logger';

import { mem0Agent } from './agents';

export const mastra = new Mastra({
  agents: { mem0Agent },
  logger: createLogger({
    name: 'Mastra',
    level: 'debug',
  }),
});
