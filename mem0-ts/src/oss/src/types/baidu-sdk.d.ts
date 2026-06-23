declare module "@baiducloud/sdk" {
  export interface BaiduCredentials {
    account: string;
    apiKey: string;
  }

  export interface BaiduConfigurationOptions {
    credentials: BceCredentials;
    endpoint: string;
  }

  export interface BaiduRow {
    id: string;
    data?: string;
    textLemmatized?: string;
    metadata?: Record<string, unknown>;
    score?: number;
    [key: string]: unknown;
  }

  export interface BaiduSearchItem {
    id?: string;
    metadata?: Record<string, unknown>;
    row?: BaiduRow;
    score?: number;
    [key: string]: unknown;
  }

  export interface BaiduSearchEnvelope {
    row?: BaiduRow;
    rows?: BaiduSearchItem[];
    points?: BaiduSearchItem[];
    items?: BaiduSearchItem[];
    data?: BaiduSearchItem[];
    total?: number;
  }

  export interface BaiduTable {
    upsert(payload: {
      rows: Array<{
        id: string;
        vector: number[];
        data?: string;
        textLemmatized?: string;
        metadata?: Record<string, unknown>;
      }>;
    }): Promise<unknown>;
    query(payload: {
      primaryKey: { id: string };
      primary_key: { id: string };
      projections?: string[];
    }): Promise<BaiduSearchEnvelope>;
    vectorSearch(payload: {
      vectorField: string;
      vector_field: string;
      vector: number[];
      limit: number;
      filter?: string;
      config?: { ef?: number };
    }): Promise<BaiduSearchEnvelope>;
    bm25Search(payload: {
      indexName: string;
      index_name: string;
      searchText: string;
      search_text: string;
      limit: number;
      filter?: string;
    }): Promise<BaiduSearchEnvelope>;
    select(payload: {
      filter?: string;
      projections?: string[];
      limit: number;
    }): Promise<BaiduSearchEnvelope>;
    delete(payload: {
      primaryKey: { id: string };
      primary_key: { id: string };
    }): Promise<unknown>;
    stats(): { tableName?: string } | Promise<{ tableName?: string }>;
  }

  export interface BaiduDatabase {
    createTable(spec: Record<string, unknown>): Promise<BaiduTable>;
    create_table(spec: Record<string, unknown>): Promise<BaiduTable>;
    describeTable(tableName: string): Promise<BaiduTable>;
    describe_table(tableName: string): Promise<BaiduTable>;
    table(tableName: string): BaiduTable;
    dropTable(tableName: string): Promise<unknown>;
    drop_table(tableName: string): Promise<unknown>;
  }

  export interface BaiduClient {
    createDatabase(name: string): Promise<BaiduDatabase>;
    create_database(name: string): Promise<BaiduDatabase>;
    database(name: string): BaiduDatabase;
  }

  export interface BaiduSdkModule {
    Configuration?: typeof Configuration;
    configuration?: typeof Configuration;
    BceCredentials?: typeof BceCredentials;
    bceCredentials?: typeof BceCredentials;
    MochowClient?: typeof MochowClient;
    mochowClient?: typeof MochowClient;
  }

  export class Configuration {
    constructor(options: BaiduConfigurationOptions);
  }

  export class BceCredentials {
    readonly account: string;
    readonly apiKey: string;
    constructor(account: string, apiKey: string);
  }

  export class MochowClient {
    constructor(configuration: Configuration);
    createDatabase(name: string): Promise<BaiduDatabase>;
    create_database(name: string): Promise<BaiduDatabase>;
    database(name: string): BaiduDatabase;
  }

  export const configuration: typeof Configuration;
  export const bceCredentials: typeof BceCredentials;
  export const mochowClient: typeof MochowClient;
}
