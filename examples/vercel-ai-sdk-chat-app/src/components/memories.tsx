import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@radix-ui/react-scroll-area";
import { Memory } from "../types";
import GlobalContext from "@/contexts/GlobalContext";
import { useContext } from "react";
import {  motion } from "framer-motion";


// eslint-disable-next-line @typescript-eslint/no-unused-vars
const MemoryItem = ({ memory }: { memory: Memory; index: number }) => {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.3 }}
      key={memory.id}
      className="space-y-2"
    >
      <div className="flex items-start justify-between">
        <p className="text-sm font-medium">{memory.content}</p>
      </div>
      <div className="flex items-center space-x-2 text-xs text-muted-foreground">
        <span>{new Date(memory.timestamp).toLocaleString()}</span>
      </div>
      <div className="flex flex-wrap gap-1">
        {memory.tags.map((tag) => (
          <Badge key={tag} variant="secondary" className="text-xs">
            {tag}
          </Badge>
        ))}
      </div>
    </motion.div>
  );
};

const Memories = (props: { isMemoriesExpanded: boolean }) => {
  const { isMemoriesExpanded } = props;
  const { memories } = useContext(GlobalContext);

  return (
    <Card
      className={`border-l rounded-none flex flex-col transition-all duration-300 ${
        isMemoriesExpanded ? "w-80" : "w-0 overflow-hidden"
      }`}
    >
      <div className="px-4 py-[22px] border-b">
        <span className="font-semibold">
          Relevant Memories ({memories.length})
        </span>
      </div>
      {memories.length === 0 && (
        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="p-4 text-center"
        >
          <span className="font-semibold">No relevant memories found.</span>
          <br />
          Only the relevant memories will be displayed here.
        </motion.div>
      )}
      <ScrollArea className="flex-1 p-4">
        <motion.div 
          className="space-y-4"
        >
          {/* <AnimatePresence mode="popLayout"> */}
            {memories.map((memory: Memory, index: number) => (
              <MemoryItem 
                key={memory.id} 
                memory={memory} 
                index={index}
              />
            ))}
          {/* </AnimatePresence> */}
        </motion.div>
      </ScrollArea>
    </Card>
  );
};

export default Memories;