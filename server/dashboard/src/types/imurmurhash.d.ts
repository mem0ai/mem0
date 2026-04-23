declare module "imurmurhash" {
  interface MurmurHash3State {
    result(): number;
    hash(value: string): MurmurHash3State;
    reset(seed?: number): MurmurHash3State;
  }
  function MurmurHash3(text?: string, seed?: number): MurmurHash3State;
  export = MurmurHash3;
}
