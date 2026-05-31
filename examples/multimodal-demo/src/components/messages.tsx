import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Message } from "../types";
import { useContext, useEffect, useRef } from "react";
import GlobalContext from "@/contexts/GlobalContext";
import Markdown from "react-markdown";
import Mem00Logo from "../assets/mem0_logo.jpeg";
import UserLogo from "../assets/user.jpg";

const Messages = () => {
  const { messages, thinking } = useContext(GlobalContext);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  // scroll to bottom
  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop += 40; // Scroll down by 40 pixels
    }
  }, [messages, thinking]);

  return (
    <>
      <ScrollArea ref={scrollAreaRef} className="flex-1 p-4 pr-10">
        <div className="space-y-4">
          {messages.map((message: Message) => (
            <div
              key={message.id}
              className={`flex ${
                message.sender === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`flex items-start space-x-2 max-w-[80%] ${
                  message.sender === "user"
                    ? "flex-row-reverse space-x-reverse"
                    : "flex-row"
                }`}
              >
                <div className="h-full flex flex-col items-center justify-end">
                  <Avatar className="h-8 w-8">
                    <AvatarImage
                      src={
                        message.sender === "assistant" ? Mem00Logo : UserLogo
                      }
                    />
                    <AvatarFallback>
                      {message.sender === "assistant" ? "AI" : "U"}
                    </AvatarFallback>
                  </Avatar>
                </div>
                <div
                  className={`rounded-xl px-3 py-2 ${
                    message.sender === "user"
                      ? "bg-blue-500 text-white rounded-br-none"
                      : "bg-muted text-muted-foreground rounded-bl-none"
                  }`}
                >
                  {message.image && (
                    <div className="w-44 flex items-center justify-center overflow-hidden rounded-lg">
                      <img
                        src={message.image}
                        alt="Message attachment"
                        className="my-2 rounded-lg max-w-full h-auto w-44 mx-auto"
                      />
                    </div>
                  )}
                  <Markdown>{message.content}</Markdown>
                  <span className="text-xs opacity-50 mt-1 block text-end relative bottom-1 -mb-2">
                    {message.timestamp}
                  </span>
                </div>
              </div>
            </div>
          ))}
          {thinking && (
            <div className={`flex justify-start`}>
              <div
                className={`flex items-start space-x-2 max-w-[80%] flex-row`}
              >
                <Avatar className="h-8 w-8">
                  <AvatarImage src={Mem00Logo} />
                  <AvatarFallback>{"AI"}</AvatarFallback>
                </Avatar>
                <div
                  className={`rounded-lg p-3 bg-muted text-muted-foreground`}
                >
                  <div className="loader">
                    <div className="ball"></div>
                    <div className="ball"></div>
                    <div className="ball"></div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>
    </>
  );
};

export default Messages;
