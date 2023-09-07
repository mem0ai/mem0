import type { LoaderResult, QnaPair } from '../models';
import { BaseLoader } from './BaseLoader';

class LocalQnaPairLoader extends BaseLoader {
  // eslint-disable-next-line class-methods-use-this
  async loadData(content: QnaPair): Promise<LoaderResult> {
    const [question, answer] = content;
    const contentText = `Q: ${question}\nA: ${answer}`;
    const metaData = {
      url: 'local',
    };
    return [
      {
        content: contentText,
        metaData,
      },
    ];
  }
}

export { LocalQnaPairLoader };
