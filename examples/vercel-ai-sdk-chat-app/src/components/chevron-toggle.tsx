import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight } from "lucide-react";
import React from "react";

const ChevronToggle = (props: {
  isMemoriesExpanded: boolean;
  setIsMemoriesExpanded: React.Dispatch<React.SetStateAction<boolean>>;
}) => {
  const { isMemoriesExpanded, setIsMemoriesExpanded } = props;
  return (
    <>
      <div className="relaive">
        <div className="flex items-center absolute top-1/2 z-10">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 border-y border rounded-lg relative right-10"
            onClick={() => setIsMemoriesExpanded(!isMemoriesExpanded)}
            aria-label={
              isMemoriesExpanded ? "Collapse memories" : "Expand memories"
            }
          >
            {isMemoriesExpanded ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <ChevronLeft className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>
    </>
  );
};

export default ChevronToggle;
