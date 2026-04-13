import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card";
import { createPortal } from "react-dom";

export const TruncatedText: React.FC<{ text: string; limit?: number }> = ({
  text,
  limit = 100,
}) => {
  if (!text) return null;
  if (text.length <= limit) return <span>{text}</span>;

  return (
    <HoverCard>
      <HoverCardTrigger asChild>
        <span className="cursor-pointer">{text?.slice(0, limit)}...</span>
      </HoverCardTrigger>
      {createPortal(
        <HoverCardContent
          className="text-foreground p-4 shadow-lg rounded-lg z-[9999]"
          style={{
            minWidth: "400px",
            maxWidth: "600px",
            width: "auto", // Allows it to adapt based on content
            transform: "translateY(10px)",
            whiteSpace: "normal", // Wraps text to prevent overflow
            overflowWrap: "break-word", // Breaks long words to fit within max-width
          }}
        >
          <p className="">{text}</p>
        </HoverCardContent>,
        document.body,
      )}
    </HoverCard>
  );
};
