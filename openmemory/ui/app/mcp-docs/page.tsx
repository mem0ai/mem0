"use client";

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { BookOpen, Shield, GitBranch, Puzzle, Terminal, Copy, Check, Code, Bot, Users, Brain } from 'lucide-react';
import { useRouter } from 'next/navigation';

// --- Reusable Components ---

// CodeBlock for syntax-highlighted code with a copy button
const CodeBlock = ({ code, lang = 'bash' }: { code: string, lang?: string }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code.trim());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  
  const lines = code.trim().split('\\n');

  return (
    <div className="relative group my-4 bg-slate-900/70 rounded-lg border border-slate-700/50 shadow-lg">
      <div className="flex text-xs text-slate-400 border-b border-slate-700/50">
        <div className="px-4 py-2 ">{lang.toUpperCase()}</div>
      </div>
      <div className="p-4 pr-12 text-sm font-mono overflow-x-auto">
        {lines.map((line, i) => {
          let styledLine = line;
          // Basic syntax highlighting
          if (lang === 'bash') {
              styledLine = styledLine.replace(/^(#.*$)/gm, '<span class="text-slate-500">$&</span>');
              styledLine = styledLine.replace(/\b(pip|npx|https|git)\b/g, '<span class="text-pink-400">$&</span>');
          } else if (lang === 'python') {
              styledLine = styledLine.replace(/(#.*$)/gm, '<span class="text-slate-500">$&</span>');
              styledLine = styledLine.replace(/(".*?"|'.*?')/g, '<span class="text-emerald-400">$&</span>');
              styledLine = styledLine.replace(/\b(from|import|def|return|print|if|for|in|not|async|await|with|as|class|try|finally|raise)\b/g, '<span class="text-pink-400">$&</span>');
              styledLine = styledLine.replace(/\b(self|True|False|None)\b/g, '<span class="text-sky-400">$&</span>');
              styledLine = styledLine.replace(/\b([A-Z_][A-Z0-9_]+)\b/g, '<span class="text-amber-300">$&</span>');
          }
          return (
            <div key={i} className="flex items-start">
              <span className="text-right text-slate-600 select-none mr-4" style={{ minWidth: '1.5em' }}>{i + 1}</span>
              <code className="text-slate-200 whitespace-pre-wrap" dangerouslySetInnerHTML={{ __html: styledLine }} />
            </div>
          )
        })}
      </div>
      <button
        onClick={handleCopy}
        className="absolute top-10 right-2 p-2 rounded-md bg-slate-700/50 hover:bg-slate-700 transition-colors opacity-0 group-hover:opacity-100"
        aria-label="Copy code"
      >
        {copied ? <Check className="h-4 w-4 text-green-400" /> : <Copy className="h-4 w-4 text-slate-400" />}
      </button>
    </div>
  );
};

// --- Main Page Component ---

const MCPDocsPage = () => {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const [activeId, setActiveId] = useState('introduction');
  
  const navItems = [
    { href: '#introduction', label: 'Introduction', icon: BookOpen },
    { href: '#connection', label: 'Connection', icon: Shield },
    { href: '#tool-reference', label: 'Tool Reference', icon: GitBranch },
    { href: '#use-case-personal', label: 'Use Case: Personal Agent', icon: Bot },
    { href: '#use-case-squad', label: 'Use Case: Agent Squad', icon: Users },
  ];

  // --- Authentication and Scroll Logic ---
  useEffect(() => {
    if (!isLoading && !user) {
      router.push('/auth');
    }
  }, [user, isLoading, router]);

  useEffect(() => {
    const handleScroll = () => {
      let currentId = '';
      for (const item of navItems) {
        const element = document.getElementById(item.href.substring(1));
        if (element && window.scrollY >= element.offsetTop - 100) {
          currentId = item.href.substring(1);
        }
      }
      if (currentId) setActiveId(currentId);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleNavClick = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    e.preventDefault();
    setActiveId(href.substring(1));
    const element = document.getElementById(href.substring(1));
    element?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    router.push(href, { scroll: false });
  };

  // --- Render Logic ---
  if (isLoading || !user) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-white">Loading...</div>
      </div>
    );
  }

  const mcpUrl = `https://api.jeanmemory.com/mcp/claude/sse/${user.id}`;
  const clientName = "my-agent";

  return (
    <div className="min-h-screen bg-slate-950 text-slate-300">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col lg:flex-row">

          {/* Sidebar */}
          <aside className="w-full lg:w-64 lg:pr-8 lg:sticky lg:top-16 self-start py-8">
            <h3 className="font-semibold text-slate-100 mb-4">MCP Agent Docs</h3>
            <nav className="space-y-2">
              {navItems.map(({ href, label, icon: Icon }) => (
                <a 
                  key={href} href={href} onClick={(e) => handleNavClick(e, href)}
                  className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    activeId === href.substring(1) ? 'bg-slate-800 text-purple-300' : 'text-slate-400 hover:bg-slate-900 hover:text-white'
                  }`}
                >
                  <Icon className="w-4 h-4" /> <span>{label}</span>
                </a>
              ))}
            </nav>
          </aside>

          {/* Main Content */}
          <main className="w-full lg:pl-8 py-16">
            <div className="max-w-3xl mx-auto space-y-16">
              
              <section id="introduction">
                <h1 className="text-4xl font-bold text-slate-100 mb-4">Building Agents with Jean Memory</h1>
                <p className="text-lg text-slate-400">
                  This documentation provides a practical guide for integrating Jean Memory into your AI agents using the Model Context Protocol (MCP). MCP allows your agent to connect to a secure, persistent memory layer, enabling complex and stateful behavior.
                </p>
              </section>

              <section id="connection">
                <h2 className="text-3xl font-bold text-slate-100 mb-4">Connection & Integration</h2>
                <p className="text-slate-400 mb-6">
                  To build an agent that uses Jean Memory, you need to establish a client connection to the MCP server. This can be done by using Anthropic's official Python SDK.
                </p>

                <h3 className="text-xl font-semibold text-slate-200 mt-4 mb-2">Step 1: Install the SDK</h3>
                <p className="text-slate-400">The MCP client is available as a Python package.</p>
                <CodeBlock code={`pip install "mcp[cli]"`} lang="bash" />

                <h3 className="text-xl font-semibold text-slate-200 mt-6 mb-2">Step 2: Configure Your Client</h3>
                <p className="text-slate-400">
                  Your script will need to connect to your personalized MCP endpoint. This URL contains your unique User ID.
                </p>
                <CodeBlock code={`YOUR_MCP_URL = "${mcpUrl}"`} lang="text" />
                <p className="text-slate-400 mt-4">Here is a basic Python script to create a session. This forms the foundation of your agent.</p>
                <CodeBlock lang="python" code={`
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_URL = "${mcpUrl}"
CLIENT_NAME = "${clientName}" # A name for your agent or application

async def create_agent_session():
    # The streamablehttp_client handles the connection to the remote server
    async with streamablehttp_client(MCP_URL) as (read, write, _):
        # ClientSession manages the MCP communication protocol
        async with ClientSession(read, write, client_name=CLIENT_NAME) as session:
            await session.initialize()
            print("✅ Agent session initialized successfully!")
            
            # You can now use the session to call tools
            # For example, let's list available tools:
            tools_response = await session.list_tools()
            print("🛠️ Available Tools:", [t.name for t in tools_response.tools])
            
            return session

# To run this:
# asyncio.run(create_agent_session())
                `} />
              </section>

              <section id="tool-reference">
                <h2 className="text-3xl font-bold text-slate-100 mb-4">Tool Reference</h2>
                <p className="text-slate-400 mb-8">
                  Once connected, your agent can call the following tools using the `session.call_tool()` method.
                </p>
                
                {/* add_memories */}
                <div>
                  <h3 className="text-xl font-semibold text-slate-200">add_memories</h3>
                  <p className="mt-1 text-slate-400">Adds one or more new memories. This is the primary way to give an agent long-term memory.</p>
                  <CodeBlock lang="python" code={`
# Coroutine
await session.call_tool(
    "add_memories", 
    {"text": "The user's favorite color is blue."}
)
                  `} />
                </div>
                
                {/* search_memory */}
                <div className="mt-8">
                  <h3 className="text-xl font-semibold text-slate-200">search_memory</h3>
                  <p className="mt-1 text-slate-400">Performs a semantic search over all memories and returns the most relevant results.</p>
                  <CodeBlock lang="python" code={`
# Coroutine
results = await session.call_tool(
    "search_memory", 
    {
        "query": "what is the user's favorite color?",
        "limit": 5 # Optional, defaults to 10
    }
)
# results.content will be a JSON string of memory objects
                  `} />
                </div>

                {/* list_memories */}
                <div className="mt-8">
                  <h3 className="text-xl font-semibold text-slate-200">list_memories</h3>
                  <p className="mt-1 text-slate-400">Retrieves the most recent memories without a search query.</p>
                  <CodeBlock lang="python" code={`
# Coroutine
results = await session.call_tool(
    "list_memories", 
    {"limit": 10} # Optional, defaults to 20
)
                  `} />
                </div>
              </section>

              <section id="use-case-personal">
                <h2 className="text-3xl font-bold text-slate-100 mb-4">Use Case: Personal Memory Agent</h2>
                <p className="text-slate-400 mb-6">
                  This example shows how to build a simple agent that remembers and recalls facts about a single user. The agent logic would be built on top of the `create_agent_session` function from before.
                </p>
                <CodeBlock lang="python" code={`
class PersonalAgent:
    def __init__(self, session):
        self.session = session

    async def remember(self, fact: str):
        print(f"🧠 Remembering: {fact}")
        await self.session.call_tool("add_memories", {"text": fact})
        print("✅ Fact stored.")

    async def recall(self, question: str):
        print(f"🤔 Recalling facts about: {question}")
        response = await self.session.call_tool("search_memory", {"query": question})
        
        # The tool returns a JSON string in the content field
        import json
        memories = json.loads(response.content[0].text)
        
        if not memories:
            return "I don't have any memories about that."
        
        # In a real agent, you would feed these memories to an LLM to synthesize an answer.
        # For this example, we'll just return the content of the most relevant memory.
        return memories[0].get('memory', 'Could not parse memory.')

async def run_personal_agent_demo():
    async with streamablehttp_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write, client_name=CLIENT_NAME) as session:
            await session.initialize()
            agent = PersonalAgent(session)
            
            await agent.remember("My dog's name is Sparky.")
            answer = await agent.recall("What is my pet's name?")
            print(f"💡 Answer: {answer}")

# To run: asyncio.run(run_personal_agent_demo())
                `} />
              </section>
              
              <section id="use-case-squad">
                <h2 className="text-3xl font-bold text-slate-100 mb-4">Use Case: Collaborative Agent Squad</h2>
                <p className="text-slate-400 mb-6">
                  To have multiple agents collaborate, they simply need to connect to the **same MCP endpoint** with the **same `client_name`**. This scopes their memory to a shared context, acting like a shared "whiteboard".
                </p>
                <p className="text-slate-400 mb-6">
                  Imagine a "Research Squad" with two agents: a `WebSearchAgent` and a `SummaryAgent`.
                </p>
                <CodeBlock lang="python" code={`
# Both agents would use the same MCP_URL and the same CLIENT_NAME
SQUAD_CLIENT_NAME = "research-squad-alpha"

# --- WebSearchAgent ---
# This agent would search the web, find facts, and call:
await session.call_tool(
    "add_memories",
    {"text": "Fact: Jupiter is the largest planet in our solar system."}
)

# --- SummaryAgent ---
# This agent would later retrieve all facts to create a summary:
response = await session.call_tool("search_memory", {"query": "facts about Jupiter"})
# It then feeds these facts to an LLM to generate a report.
                `} />
                 <p className="mt-4 text-slate-400">
                  By sharing a memory space via the `client_name`, the `SummaryAgent` can access the information gathered by the `WebSearchAgent`, enabling true collaboration.
                </p>
              </section>

              <section>
                <h2 className="text-3xl font-bold text-slate-100 flex items-center">
                  <span className="flex items-center justify-center w-8 h-8 rounded-full bg-purple-500/20 text-purple-300 mr-4">2</span>
                  Connect Your Agent
                </h2>
                <p className="mt-4 text-slate-400">
                  To connect a compatible agent like Claude, run the official `install-mcp` command in your terminal. This command configures your local agent environment to communicate with your Jean Memory server.
                </p>
                <CodeBlock lang="bash" code={`npx install-mcp ${mcpUrl} --client ${clientName}`} />
                <p className="mt-4 text-slate-400">
                  Once this command is running, your AI agent's environment is connected to Jean Memory. The agent can now use any of the available memory tools.
                </p>
              </section>

            </div>
          </main>
        </div>
      </div>
    </div>
  );
};

export default MCPDocsPage; 