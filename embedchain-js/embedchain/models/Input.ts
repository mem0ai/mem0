import type { QnaPair } from './QnAPair';

export type RemoteInput = string;

export type LocalInput = QnaPair;

export type Input = RemoteInput | LocalInput;
