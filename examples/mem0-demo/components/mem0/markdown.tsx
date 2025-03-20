"use client"

import { CSSProperties, useState, ReactNode, useRef } from "react"
import React from "react"
import Markdown, { Components } from "react-markdown"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { coldarkCold, coldarkDark } from "react-syntax-highlighter/dist/esm/styles/prism"
import remarkGfm from "remark-gfm"
import remarkMath from "remark-math"
import { Button } from "@/components/ui/button"
import { Check, Copy } from "lucide-react"
import { cn } from "@/lib/utils"
import "./markdown.css"

interface MarkdownRendererProps {
  markdownText: string
  actualCode?: string
  className?: string
  style?: { prism?: { [key: string]: CSSProperties } }
  messageId?: string
  showCopyButton?: boolean
  isDarkMode?: boolean
}

const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ 
  markdownText = '',
  className, 
  style,
  actualCode, 
  messageId = '', 
  showCopyButton = true,
  isDarkMode = false
}) => {
  const [copied, setCopied] = useState(false);
  const [isStreaming, setIsStreaming] = useState(true);
  const highlightBuffer = useRef<string[]>([]);
  const isCollecting = useRef(false);
  const processedTextRef = useRef<string>('');

  const safeMarkdownText = React.useMemo(() => {
    return typeof markdownText === 'string' ? markdownText : '';
  }, [markdownText]);

  const preProcessText = React.useCallback((text: unknown): string => {
    if (typeof text !== 'string' || !text) return '';
    
    // Remove highlight tags initially for clean rendering
    return text.replace(/<highlight>.*?<\/highlight>/g, (match) => {
      // Extract the content between tags
      const content = match.replace(/<highlight>|<\/highlight>/g, '');
      return content;
    });
  }, []);

  // Reset streaming state when markdownText changes
  React.useEffect(() => {
    // Preprocess the text first
    processedTextRef.current = preProcessText(safeMarkdownText);
    setIsStreaming(true);
    const timer = setTimeout(() => {
      setIsStreaming(false);
    }, 500);
    return () => clearTimeout(timer);
  }, [safeMarkdownText, preProcessText]);

  const copyToClipboard = async (code: string) => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1000);
  };

  const processText = React.useCallback((text: string) => {
    if (typeof text !== 'string') return text;
    
    // Only process highlights after streaming is complete
    if (!isStreaming) {
      if (text === '<highlight>') {
        isCollecting.current = true;
        return null;
      }

      if (text === '</highlight>') {
        isCollecting.current = false;
        const content = highlightBuffer.current.join('');
        highlightBuffer.current = [];

        return (
          <span 
            key={`highlight-${messageId}-${content}`}
            className={cn("highlight-text animate text-black", {
              "dark": isDarkMode
            })}
          >
            {content}
          </span>
        );
      }

      if (isCollecting.current) {
        highlightBuffer.current.push(text);
        return null;
      }
    }

    return text;
  }, [isStreaming, messageId, isDarkMode]);

  const processChildren = React.useCallback((children: ReactNode): ReactNode => {
    if (typeof children === 'string') {
      return processText(children);
    }
    if (Array.isArray(children)) {
      return children.map(child => {
        const processed = processChildren(child);
        return processed === null ? null : processed;
      }).filter(Boolean);
    }
    return children;
  }, [processText]);

  const CodeBlock = React.useCallback(({
    language,
    code,
    actualCode,
    showCopyButton = true,
  }: {
    language: string;
    code: string;
    actualCode?: string;
    showCopyButton?: boolean;
  }) => (
    <div className="relative my-4 rounded-xl overflow-hidden bg-neutral-100 w-full max-w-full border border-neutral-200">
      {showCopyButton && (
        <div className="flex items-center justify-between px-4 py-2 rounded-t-md shadow-md">
          <span className="text-xs text-neutral-700 dark:text-white font-inter-display">
            {language}
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-neutral-700 dark:text-white"
            onClick={() => copyToClipboard(actualCode || code)}
          >
            {copied ? (
              <Check className="h-4 w-4 text-green-500" />
            ) : (
              <Copy className="h-4 w-4 text-muted-foreground" />
            )}
          </Button>
        </div>
      )}
      <div className="max-w-full w-full overflow-hidden">
        <SyntaxHighlighter
          language={language}
          style={style?.prism || (isDarkMode ? coldarkDark : coldarkCold)}
          customStyle={{
            margin: 0,
            borderTopLeftRadius: "0",
            borderTopRightRadius: "0",
            padding: "16px",
            fontSize: "0.9rem",
            lineHeight: "1.3",
            backgroundColor: isDarkMode ? "#262626" : "#fff",
            wordBreak: "break-word",
            overflowWrap: "break-word",
          }}
        >
          {code}
        </SyntaxHighlighter>
      </div>
    </div>
  ), [copied, isDarkMode, style]);

  const components = {
    p: ({ children, ...props }: React.HTMLAttributes<HTMLParagraphElement>) => (
      <p className="m-0 p-0" {...props}>{processChildren(children)}</p>
    ),
    span: ({ children, ...props }: React.HTMLAttributes<HTMLSpanElement>) => (
      <span {...props}>{processChildren(children)}</span>
    ),
    li: ({ children, ...props }: React.HTMLAttributes<HTMLLIElement>) => (
      <li {...props}>{processChildren(children)}</li>
    ),
    strong: ({ children, ...props }: React.HTMLAttributes<HTMLElement>) => (
      <strong {...props}>{processChildren(children)}</strong>
    ),
    em: ({ children, ...props }: React.HTMLAttributes<HTMLElement>) => (
      <em {...props}>{processChildren(children)}</em>
    ),
    code: ({ className, children, ...props }: React.HTMLAttributes<HTMLElement>) => {
      const match = /language-(\w+)/.exec(className || "");
      if (match) {
        return (
          <CodeBlock
            language={match[1]}
            code={String(children)}
            actualCode={actualCode}
            showCopyButton={showCopyButton}
          />
        );
      }
      return (
        <code className={className} {...props}>
          {processChildren(children)}
        </code>
      );
    }
  } satisfies Components;

  return (
    <div className={cn(
      "min-w-[100%] max-w-[100%] my-2 prose-hr:my-0 prose-h4:my-1 text-sm prose-ul:-my-2 prose-ol:-my-2 prose-li:-my-2 prose break-words prose-pre:bg-transparent prose-pre:-my-2 dark:prose-invert prose-p:leading-snug prose-pre:p-0 prose-h3:-my-2 prose-p:-my-2",
      className
    )}>
      <Markdown
        remarkPlugins={[remarkGfm, remarkMath]}
        components={components}
      >
        {(isStreaming ? processedTextRef.current : safeMarkdownText)}
      </Markdown>
      {(isStreaming || (!isStreaming && !processedTextRef.current)) && <span className="markdown-cursor">▋</span>}
    </div>
  );
};

export default MarkdownRenderer;
