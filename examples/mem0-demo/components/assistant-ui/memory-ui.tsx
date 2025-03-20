import { useMessage } from "@assistant-ui/react";
import { FC, useMemo } from "react";
import MemoryIndicator, { Memory } from "./memory-indicator";

type RetrievedMemory = {
  isNew: boolean;
  id: string;
  memory: string;
  user_id: string;
  categories: readonly string[];
  immutable: boolean;
  created_at: string;
  updated_at: string;
  score: number;
};

type NewMemory = {
  id: string;
  data: {
    memory: string;
  };
  event: "ADD" | "DELETE";
};

type NewMemoryAnnotation = {
  readonly type: "mem0-update";
  readonly memories: readonly NewMemory[];
};

type GetMemoryAnnotation = {
  readonly type: "mem0-get";
  readonly memories: readonly RetrievedMemory[];
};

type MemoryAnnotation = NewMemoryAnnotation | GetMemoryAnnotation;

const isMemoryAnnotation = (a: unknown): a is MemoryAnnotation =>
  typeof a === "object" &&
  a != null &&
  "type" in a &&
  (a.type === "mem0-update" || a.type === "mem0-get");

const useMemories = (): Memory[] => {
  const annotations = useMessage((m) => m.metadata.unstable_annotations);
  console.log("annotations", annotations);
  return useMemo(
    () =>
      annotations?.filter(isMemoryAnnotation).flatMap((a) => {
        if (a.type === "mem0-update") {
          return a.memories.map(
            (m): Memory => ({
              event: m.event,
              id: m.id,
              memory: m.data.memory,
              score: 1,
            })
          );
        } else if (a.type === "mem0-get") {
          return a.memories.map((m) => ({
            event: "GET",
            id: m.id,
            memory: m.memory,
            score: m.score,
          }));
        }
        throw new Error("Unexpected annotation: " + JSON.stringify(a));
      }) ?? [],
    [annotations]
  );
};

export const MemoryUI: FC = () => {
  const memories = useMemories();

  return (
    <div className="flex mb-1">
      <MemoryIndicator memories={memories} />
    </div>
  );
};
