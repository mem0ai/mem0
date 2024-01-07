"use client";

import { useState, useEffect } from "react";
import { Separator } from "@/components/ui/separator";
import { ChatCard } from "@/components/chat";
import Link from "next/link";

function generateSessionId() {
  return Date.now().toString();
}

export default function Page() {
  const [sessionId, setSessionId] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) {
      // Generate a new session ID (you can use any method to generate an ID)
      const newSessionId = generateSessionId(); // Replace this with your own logic
      setSessionId(newSessionId);
    }
  }, [sessionId]);

  return (
    <div className="mt-20 flex justify-center items-stretch">
      <div className="max-w-screen-lg w-full bg-background">
        <div className="p-4 md:p-8 flex flex-col">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              {" "}
              {/* Right-align heading and tooltip */}
              <h2 className="text-2xl font-semibold tracking-tight">
                Chat with your documents
              </h2>
            </div>
          </div>
          <h3 className="text-sm text-muted-foreground">
            Built using{" "}
            <Link
              className="text-gray-900 underline underline-offset-2"
              href="https://github.com/embedchain/embedchain"
              target="_blank"
            >
              Embedchain
            </Link>{" "}
            ❤️
          </h3>
          <Separator className="my-4" />
          <div className="flex-1 overflow-y-auto max-h-fit">
            {sessionId !== null && <ChatCard sessionId={sessionId} />}
          </div>
        </div>
      </div>
    </div>
  );
}
