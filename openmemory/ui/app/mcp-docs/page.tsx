"use client";

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { BookOpen, Shield, GitBranch, Puzzle, Terminal, Copy, Check, Bot, Users } from 'lucide-react';
import { useRouter } from 'next/navigation';

// --- Reusable Components ---
const CodeBlock = ({ code }: { code: string }) => {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(code.trim());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group my-4 bg-slate-900 rounded-lg border border-slate-700/50 shadow-lg">
      <pre className="p-4 text-sm font-mono overflow-x-auto text-slate-200 whitespace-pre-wrap">
        <code>{code.trim()}</code>
      </pre>
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 p-2 rounded-md bg-slate-800/50 hover:bg-slate-700 transition-colors opacity-0 group-hover:opacity-100"
        aria-label="Copy code"
      >
        {copied ? <Check className="h-4 w-4 text-green-400" /> : <Copy className="h-4 w-4 text-slate-400" />}
      </button>
    </div>
  );
};

const DocsHeader = ({ title, subtitle }: { title: string, subtitle: string }) => (
    <section>
        <h1 className="text-4xl font-bold text-slate-100 mb-2">{title}</h1>
        <p className="text-lg text-slate-400">{subtitle}</p>
    </section>
);

const DocsSection = ({ id, title, children }: { id: string, title: string, children: React.ReactNode }) => (
    <section id={id} className="pt-8">
        <h2 className="text-2xl font-semibold text-slate-200 mb-4">{title}</h2>
        <div className="space-y-4 text-slate-300">{children}</div>
    </section>
);


// --- Main Page Component ---
const MCPDocsPage = () => {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const [activeId, setActiveId] = useState('introduction');
  
  const navItems = [
    { href: '#introduction', label: 'Introduction' },
    { href: '#connecting', label: 'Connecting Your Agent' },
    { href: '#tool-reference', label: 'Tool Reference' },
    { href: '#full-example', label: 'Full Agent Example' },
    { href: '#collaboration', label: 'Agent Collaboration' },
  ];

  // --- Auth & Scroll Logic ---
  useEffect(() => {
    if (!isLoading && !user) router.push('/auth');
  }, [user, isLoading, router]);

  useEffect(() => {
    const handleScroll = () => {
      for (const item of navItems) {
        const element = document.getElementById(item.href.substring(1));
        if (element && window.scrollY >= element.offsetTop - 100) {
          setActiveId(item.href.substring(1));
          break;
        }
      }
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleNavClick = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    e.preventDefault();
    const element = document.getElementById(href.substring(1));
    element?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    router.push(href, { scroll: false });
  };

  if (isLoading || !user) {
    return <div className="min-h-screen bg-slate-950 flex items-center justify-center text-white">Loading...</div>;
  }

  const mcpUrl = `https://api.jeanmemory.com/mcp/claude/sse/${user.id}`;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-300">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col lg:flex-row">

          {/* Sidebar */}
          <aside className="w-full lg:w-56 lg:pr-8 lg:sticky lg:top-16 self-start py-8">
            <nav className="space-y-2">
              {navItems.map(({ href, label }) => (
                <a 
                  key={href} href={href} onClick={(e) => handleNavClick(e, href)}
                  className={`block px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    activeId === href.substring(1) ? 'bg-slate-800 text-purple-300' : 'text-slate-400 hover:bg-slate-900 hover:text-white'
                  }`}
                >
                  {label}
                </a>
              ))}
            </nav>
          </aside>

          {/* Main Content */}
          <main className="w-full lg:pl-8 py-16">
            <div className="max-w-3xl mx-auto space-y-12">
              
              <DocsHeader title="Agent Integration Guide" subtitle="Connect stateful AI agents to Jean Memory using the Model Context Protocol (MCP)." />

              <DocsSection id="introduction" title="Introduction">
                <p>MCP provides a persistent, stateful connection between your AI agent and the Jean Memory service. Instead of a stateless request/response cycle over HTTP, agents call named tools over a session. This guide provides the practical steps to integrate your agent from scratch using Python.</p>
              </DocsSection>

              <DocsSection id="connecting" title="Connecting Your Agent">
                <p>Your agent will need to connect to your personal MCP endpoint URL. This URL is unique to your user account.</p>
                <CodeBlock code={`# Your personal MCP endpoint URL
MCP_URL = "${mcpUrl}"`} />
                <p>To connect, you must use Anthropic's official Python SDK. This library handles the low-level details of the MCP connection.</p>
                <CodeBlock code={`pip install "mcp[cli]"`} />
                <p>The following Python script establishes a connection and lists the tools available to your agent. This is the foundation for any agent you build.</p>
                <CodeBlock code={`import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# Your personal URL from the docs page
MCP_URL = "${mcpUrl}"
CLIENT_NAME = "my-personal-agent" # A unique name for your agent

async def connect_and_list_tools():
    """Establishes a connection and lists available tools."""
    try:
        async with streamablehttp_client(MCP_URL) as (read, write, _):
            async with ClientSession(read, write, client_name=CLIENT_NAME) as session:
                await session.initialize()
                print("✅ Agent session initialized successfully!")
                
                tools_response = await session.list_tools()
                print("🛠️ Available Tools:", [t.name for t in tools_response.tools])
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(connect_and_list_tools())`} />
              </DocsSection>

              <DocsSection id="tool-reference" title="Tool Reference">
                <p>Once a session is established, your agent can use `session.call_tool()` to interact with its memory.</p>
                <h4 className="font-semibold text-slate-200 pt-4">add_memories</h4>
                <p>Stores a new memory. The `text` can be any string of information.</p>
                <CodeBlock code={`await session.call_tool("add_memories", {"text": "The user is interested in generative AI."})`} />

                <h4 className="font-semibold text-slate-200 pt-4">search_memory</h4>
                <p>Performs a semantic search and returns the most relevant memories as a JSON string.</p>
                <CodeBlock code={`response = await session.call_tool("search_memory", {"query": "user interests"})
# response.content[0].text contains the JSON string of results`} />
                
                <h4 className="font-semibold text-slate-200 pt-4">list_memories</h4>
                <p>Retrieves the most recent memories without a query.</p>
                <CodeBlock code={`response = await session.call_tool("list_memories", {"limit": 10})`} />
              </DocsSection>

              <DocsSection id="full-example" title="Full Agent Example">
                <p>This complete, runnable script demonstrates a simple agent that can remember and recall information. You can save this as a `.py` file and run it directly.</p>
                <CodeBlock code={`import asyncio
import json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_URL = "${mcpUrl}"
CLIENT_NAME = "personal-memory-agent-v1"

class PersonalAgent:
    """A simple agent that connects to Jean Memory and uses its tools."""
    
    def __init__(self):
        self.session = None

    async def connect(self):
        """Initializes the connection to the MCP server."""
        print("Connecting to Jean Memory...")
        try:
            # Use an exit stack to manage resources
            from contextlib import AsyncExitStack
            self.exit_stack = AsyncExitStack()
            
            read, write, _ = await self.exit_stack.enter_async_context(streamablehttp_client(MCP_URL))
            self.session = await self.exit_stack.enter_async_context(ClientSession(read, write, client_name=CLIENT_NAME))
            
            await self.session.initialize()
            print("✅ Connection successful.")
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            await self.disconnect()
            raise

    async def disconnect(self):
        """Cleans up the connection."""
        if self.exit_stack:
            await self.exit_stack.aclose()
            print("Disconnected.")

    async def remember(self, fact: str):
        """Stores a fact in memory."""
        if not self.session: raise ConnectionError("Agent not connected.")
        print(f"🧠 Remembering: '{fact}'")
        await self.session.call_tool("add_memories", {"text": fact})

    async def recall(self, question: str) -> str:
        """Recalls information by searching memory."""
        if not self.session: raise ConnectionError("Agent not connected.")
        print(f"🤔 Recalling info about: '{question}'")
        response = await self.session.call_tool("search_memory", {"query": question})
        
        try:
            memories = json.loads(response.content[0].text)
            if not memories:
                return "I have no memory of that."
            # In a real agent, you would feed these to an LLM to synthesize a response.
            return f"I recall this: '{memories[0].get('memory')}'"
        except (json.JSONDecodeError, IndexError, KeyError):
            return "I had trouble interpreting my memories."

async def main():
    """Main function to run a demo of the agent."""
    agent = PersonalAgent()
    try:
        await agent.connect()
        await agent.remember("The user's project code is 'Bluebird'.")
        answer = await agent.recall("What is the project code?")
        print(f"💡 Agent's Answer: {answer}")
    finally:
        await agent.disconnect()

if __name__ == "__main__":
    asyncio.run(main())`} />
              </DocsSection>

              <DocsSection id="collaboration" title="Agent Collaboration">
                <p>To have multiple agents collaborate, they must connect to the same MCP endpoint and use the same `CLIENT_NAME`. This places them in a shared memory context.</p>
                <p>For example, a `ResearcherAgent` could add facts, and a `WriterAgent` could later query those facts to write a report. Both would initialize their session with `CLIENT_NAME = "research-squad-alpha"`.</p>
              </DocsSection>

            </div>
          </main>
        </div>
      </div>
    </div>
  );
};

export default MCPDocsPage; 