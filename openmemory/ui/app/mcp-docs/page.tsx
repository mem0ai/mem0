"use client";

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Terminal, Copy, Check, User, Link as LinkIcon, Shield } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

// CodeBlock component for syntax highlighting and copying
const CodeBlock = ({ code, lang = 'bash' }: { code: string, lang?: string }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code.trim());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group my-4 bg-slate-900/70 rounded-lg border border-slate-700/50 shadow-lg">
      <div className="flex text-xs text-slate-400 border-b border-slate-700/50">
        <div className="px-4 py-2 ">{lang.toUpperCase()}</div>
      </div>
      <div className="p-4 pr-12 text-sm font-mono overflow-x-auto text-slate-200">
        <code className="whitespace-pre-wrap" dangerouslySetInnerHTML={{ __html: code.trim() }} />
      </div>
      <button
        onClick={handleCopy}
        className="absolute top-10 right-2 p-2 rounded-md bg-slate-700/50 hover:bg-slate-700 transition-colors opacity-0 group-hover:opacity-100"
        aria-label="Copy code"
      >
        {copied ? (
          <Check className="h-4 w-4 text-green-400" />
        ) : (
          <Copy className="h-4 w-4 text-slate-400" />
        )}
      </button>
    </div>
  );
};

// Main component for the MCP Docs page
const MCPDocsPage = () => {
  const { user, isLoading } = useAuth();
  const [mcpUrl, setMcpUrl] = useState('');
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.push('/auth');
    }
    if (user) {
      setMcpUrl(`https://api.jeanmemory.com/mcp/claude/sse/${user.id}`);
    }
  }, [user, isLoading, router]);

  if (isLoading) {
    return <div className="flex items-center justify-center min-h-screen bg-slate-950 text-white">Loading...</div>;
  }

  if (!user) {
    return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-slate-950 text-white">
            <Shield className="w-16 h-16 text-red-500 mb-4" />
            <h1 className="text-2xl font-bold mb-2">Redirecting to login...</h1>
        </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-300">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="max-w-4xl mx-auto">
          <header className="text-center mb-16">
            <h1 className="text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-pink-500">
              Build Agents with Jean Memory
            </h1>
            <p className="text-xl text-slate-400 mt-4">
              Your personalized guide to connecting AI agents using the Model Context Protocol (MCP).
            </p>
          </header>

          <div className="space-y-12">
            
            {/* Step 1: Your Personalized Config */}
            <section>
              <h2 className="text-3xl font-bold text-slate-100 flex items-center">
                <span className="flex items-center justify-center w-8 h-8 rounded-full bg-purple-500/20 text-purple-300 mr-4">1</span>
                Your Personalized Configuration
              </h2>
              <p className="mt-4 text-slate-400">
                This is your unique connection URL. It's pre-filled with your User ID and ready to use. This URL securely points your agent to your personal memory space.
              </p>
              <CodeBlock lang="url" code={mcpUrl} />
            </section>

            {/* Step 2: Client Installation */}
            <section>
              <h2 className="text-3xl font-bold text-slate-100 flex items-center">
                <span className="flex items-center justify-center w-8 h-8 rounded-full bg-purple-500/20 text-purple-300 mr-4">2</span>
                Connect Your Agent
              </h2>
              <p className="mt-4 text-slate-400">
                The easiest way to connect your agent is with a compatible MCP client like `supergateway`. Use the command below in your terminal. It uses your personal URL to establish a persistent, secure connection.
              </p>
              <CodeBlock lang="bash" code={`npx -y supergateway --sse "${mcpUrl}"`} />
              <p className="mt-4 text-slate-400">
                Once this command is running, your AI agent's environment is connected to Jean Memory. The agent can now use any of the available memory tools.
              </p>
            </section>
            
            {/* Step 3: Example Usage */}
            <section>
              <h2 className="text-3xl font-bold text-slate-100 flex items-center">
                <span className="flex items-center justify-center w-8 h-8 rounded-full bg-purple-500/20 text-purple-300 mr-4">3</span>
                Example: Teaching Your Agent
              </h2>
              <p className="mt-4 text-slate-400">
                Now you can instruct your agent to use its new memory. The agent will automatically discover and use tools like `add_memories` and `search_memory` via the MCP connection.
              </p>
              <div className="mt-6 p-6 border border-slate-800 rounded-lg bg-slate-900/50 space-y-4">
                <h4 className="font-semibold text-lg text-slate-100">Sample Agent Conversation:</h4>
                <div className="flex items-start gap-4">
                  <User className="w-6 h-6 text-sky-400 flex-shrink-0 mt-1" />
                  <p className="text-slate-300">"Please remember that my favorite programming language is Python."</p>
                </div>
                <div className="flex items-start gap-4">
                  <Terminal className="w-6 h-6 text-emerald-400 flex-shrink-0 mt-1" />
                  <p className="italic text-slate-400">[Agent calls <code className="font-mono text-emerald-400">add_memories</code> with the text "The user's favorite programming language is Python."]</p>
                </div>
                <div className="flex items-start gap-4">
                  <User className="w-6 h-6 text-sky-400 flex-shrink-0 mt-1" />
                  <p className="text-slate-300">"What is my favorite language?"</p>
                </div>
                <div className="flex items-start gap-4">
                    <Terminal className="w-6 h-6 text-emerald-400 flex-shrink-0 mt-1" />
                  <p className="italic text-slate-400">[Agent calls <code className="font-mono text-emerald-400">search_memory</code> with the query "favorite language" and gets the previous memory back.]</p>
                </div>
                 <div className="flex items-start gap-4">
                  <LinkIcon className="w-6 h-6 text-purple-400 flex-shrink-0 mt-1" />
                  <p className="text-slate-200">"Your favorite programming language is Python."</p>
                </div>
              </div>
            </section>
            
            <footer className="text-center pt-10 border-t border-slate-800">
                <p className="text-slate-500">Looking for the traditional REST API documentation? You can find it <Link href="/api-docs" className="text-purple-400 hover:underline">here</Link>.</p>
            </footer>

          </div>
        </div>
      </div>
    </div>
  );
};

export default MCPDocsPage; 