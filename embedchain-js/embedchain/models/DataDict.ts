import type { ChunkResult } from './ChunkResult';

type Data = {
  doc: ChunkResult['documents'][0];
  meta: ChunkResult['metadatas'][0];
};

export type DataDict = {
  [id: string]: Data;
};
