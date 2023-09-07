import { RecursiveCharacterTextSplitter } from 'langchain/text_splitter';

import { BaseChunker } from './BaseChunker';

interface TextSplitterChunkParams {
  chunkSize: number;
  chunkOverlap: number;
  keepSeparator: boolean;
}

const TEXT_SPLITTER_CHUNK_PARAMS: TextSplitterChunkParams = {
  chunkSize: 300,
  chunkOverlap: 0,
  keepSeparator: false,
};

class QnaPairChunker extends BaseChunker {
  constructor() {
    const textSplitter = new RecursiveCharacterTextSplitter(
      TEXT_SPLITTER_CHUNK_PARAMS
    );
    super(textSplitter);
  }
}

export { QnaPairChunker };
