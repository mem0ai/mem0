import { VectorStoreConfig } from "./index";

export interface ValkeyConfig extends VectorStoreConfig {
  valkeyUrl: string;
  collectionName: string;
  embeddingModelDims: number;
  timezone?: string;
  indexType?: "hnsw" | "flat";
  hnswM?: number;
  hnswEfConstruction?: number;
  hnswEfRuntime?: number;
  clusterMode?: boolean;
}
