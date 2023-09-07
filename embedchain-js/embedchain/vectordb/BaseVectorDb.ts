class BaseVectorDB {
  initDb: Promise<void>;

  constructor() {
    this.initDb = this.getClientAndCollection();
  }

  // eslint-disable-next-line class-methods-use-this
  protected async getClientAndCollection(): Promise<void> {
    throw new Error('getClientAndCollection() method is not implemented');
  }
}

export { BaseVectorDB };
