import type { Input, LoaderResult } from '../models';

export abstract class BaseLoader {
  abstract loadData(src: Input): Promise<LoaderResult>;
}
