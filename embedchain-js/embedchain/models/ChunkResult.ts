import type { Metadata } from './Metadata';

export type ChunkResult = {
  documents: string[];
  ids: string[];
  metadatas: Metadata[];
};
