"use client";

import { ScrollArea } from "@/components/ui/scroll-area";
import { FileIcon } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect } from "react";

interface CodeComparisonProps {
  beforeCode: string;
  afterCode: string;
  language: string;
  filename: string;
  lightTheme: string;
  darkTheme: string;
}

export function CodeComparison({
  beforeCode,
  afterCode,
  language,
  filename,
  lightTheme,
  darkTheme,
}: CodeComparisonProps) {
  const { theme, systemTheme } = useTheme();

  useEffect(() => {
    const currentTheme = theme === "system" ? systemTheme : theme;
    const selectedTheme = currentTheme === "dark" ? darkTheme : lightTheme;
  }, [
    theme,
    systemTheme,
    beforeCode,
    afterCode,
    language,
    lightTheme,
    darkTheme,
  ]);

  
  return (
    <div className="mx-auto w-full">
      <div className="relative w-full overflow-hidden rounded-md border border-memBorder-primary">
        <div className="relative grid md:grid-cols-2 md:divide-x md:divide-memBorder-primary">
          <div className="flex flex-col overflow-hidden">
            <div className="flex items-center bg-accent p-2 text-sm text-foreground">
              <FileIcon className="mr-2 size-4" />
              {filename}
              <span className="ml-auto">before</span>
            </div>
            <ScrollArea className="h-[65vh]">
              <div className="bg-surface-default-primary p-4 text-sm text-foreground whitespace-pre-wrap">
                {beforeCode}
              </div>
            </ScrollArea>
          </div>
          <div className="flex flex-col overflow-hidden">
            <div className="flex items-center bg-accent p-2 text-sm text-foreground">
              <FileIcon className="mr-2 size-4" />
              {filename}
              <span className="ml-auto">after</span>
            </div>
            <ScrollArea className="h-[65vh]">
              <div className="bg-surface-default-primary p-4 text-sm text-foreground whitespace-pre-wrap">
                {afterCode}
              </div>
            </ScrollArea>
          </div>
        </div>
        <div className="absolute left-1/2 top-1/2 flex size-8 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-md bg-accent text-xs text-foreground">
          VS
        </div>
      </div>
    </div>
  );
}