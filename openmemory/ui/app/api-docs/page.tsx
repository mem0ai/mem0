"use client";

import React, { useState, useEffect, useRef } from 'react';
import { GitBranch, Shield, BookOpen, Puzzle, Terminal, Code, Server, Key, BrainCircuit, Copy, Check, LucideIcon, ListTree, Bot, Lightbulb, Briefcase, Share2, Component } from 'lucide-react';
import { usePathname, useRouter } from 'next/navigation';
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

// A simple syntax-highlighted code block component with a copy button
const CodeBlock = ({ code, lang = 'bash' }: { code: string, lang?: string }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code.trim());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000); // Reset after 2 seconds
  };
  
  const lines = code.trim().split('\\n');

  return (
    <div className="relative group my-4 bg-slate-900/70 rounded-lg border border-slate-700/50 shadow-lg">
      <div className="flex text-xs text-slate-400 border-b border-slate-700/50">
        <div className="px-4 py-2 ">{lang}</div>
      </div>
      <div className="p-4 pr-12 text-sm font-mono overflow-x-auto">
        {lines.map((line, i) => {
          let styledLine: string = line;
          if (lang === 'bash' || lang === 'http') {
              styledLine = line.replace(/curl/g, '<span class="text-pink-400">curl</span>');
              styledLine = styledLine.replace(/(-X POST|-H|-d)/g, '<span class="text-cyan-400">$&</span>');
              styledLine = styledLine.replace(/(https:\/\/[^\s]+)/g, '<span class="text-amber-400">$&</span>');
              styledLine = styledLine.replace(/Authorization:/g, '<span class="text-sky-400">$&</span>');
          } else if (lang === 'python') {
              styledLine = styledLine.replace(/(#.*$)/g, '<span class="text-slate-500">$&</span>');
              styledLine = styledLine.replace(/(".*?"|'.*?')/g, '<span class="text-emerald-400">$&</span>');
              styledLine = styledLine.replace(/\b(from|import|def|return|print|if|for|in|not|try|except|raise|as)\b/g, '<span class="text-pink-400">$&</span>');
              styledLine = styledLine.replace(/\b(requests|json|os)\b/g, '<span class="text-sky-400">$&</span>');
          } else if (lang === 'mermaid') {
              return <div key={i}><pre className="text-slate-200 whitespace-pre-wrap">{line}</pre></div>;
          } else if (lang === 'json') {
              styledLine = code.replace(/(".*?")/g, '<span class="text-emerald-400">$&</span>');
          }
          return (
            <div key={i} className="flex items-start">
              <span className="text-right text-slate-600 select-none mr-4" style={{ minWidth: '2em' }}>
                {i + 1}
              </span>
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
        {copied ? (
          <Check className="h-4 w-4 text-green-400" />
        ) : (
          <Copy className="h-4 w-4 text-slate-400" />
        )}
      </button>
    </div>
  );
};

// Component to render Mermaid diagrams
const MermaidDiagram = ({ chart }: { chart: string }) => {
  const ref = useRef<HTMLDivElement>(null);
  const [isRendered, setIsRendered] = useState(false);

  useEffect(() => {
    const renderMermaid = async () => {
      // Dynamically import mermaid only on the client-side
      const mermaid = (await import('mermaid')).default;
      mermaid.initialize({ 
        startOnLoad: false,
        theme: 'dark',
        darkMode: true,
        themeVariables: {
            background: '#0f172a',
            primaryColor: '#1e293b',
            primaryTextColor: '#d1d5db',
            lineColor: '#4b5563',
            textColor: '#d1d5db',
            fontSize: '14px',
        }
       });

      if (ref.current) {
        const { svg } = await mermaid.render(`mermaid-graph-${Math.random().toString(36).substring(7)}`, chart);
        ref.current.innerHTML = svg;
        setIsRendered(true);
      }
    };

    renderMermaid();
  }, [chart]);

  return (
    <div className="flex justify-center items-center p-4 bg-slate-900/70 rounded-lg border border-slate-700/50 min-h-[300px]">
       <div 
        ref={ref} 
        className={`mermaid-container ${isRendered ? 'opacity-100' : 'opacity-0'} transition-opacity duration-500`}
        // The raw chart is kept for accessibility and for mermaid to process
        style={{ display: isRendered ? 'block' : 'none' }}
      >
        {chart}
      </div>
      {!isRendered && <div className="text-slate-400">Loading diagram...</div>}
    </div>
  );
};

// Layout component for documentation pages
const DocsLayout = ({ children, navItems }: { children: React.ReactNode, navItems: { href: string, label: string, icon: LucideIcon }[] }) => {
  const [activeId, setActiveId] = useState('introduction');
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    const handleScroll = () => {
      let currentId = '';
      for (const item of navItems) {
        const element = document.getElementById(item.href.substring(1));
        if (element && window.scrollY >= element.offsetTop - 100) {
          currentId = item.href.substring(1);
        }
      }
      if (currentId) {
        setActiveId(currentId);
      }
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, [navItems]);

  const handleNavClick = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    e.preventDefault();
    setActiveId(href.substring(1));
    document.getElementById(href.substring(1))?.scrollIntoView({
      behavior: 'smooth',
      block: 'start'
    });
    router.push(`${pathname}${href}`, { scroll: false });
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-300">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col lg:flex-row">
          <aside className="w-full lg:w-64 lg:pr-8 lg:sticky lg:top-16 self-start py-8">
            <nav className="space-y-2">
              {navItems.map(({ href, label, icon: Icon }) => (
                <a
                  key={href}
                  href={href}
                  onClick={(e) => handleNavClick(e, href)}
                  className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    activeId === href.substring(1)
                      ? 'bg-slate-800 text-purple-300'
                      : 'text-slate-400 hover:bg-slate-900 hover:text-white'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{label}</span>
                </a>
              ))}
            </nav>
          </aside>
          <main className="w-full lg:pl-8 py-16">
            <div className="max-w-3xl mx-auto space-y-16">
              {children}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
};

const navItems = [
  { href: '#introduction', label: 'Introduction', icon: BookOpen },
  { href: '#authentication', label: 'Authentication', icon: Shield },
  { href: '#endpoints', label: 'API Endpoint', icon: GitBranch },
  { href: '#quick-test', label: 'Quick Test', icon: Terminal },
  { href: '#dynamic-agents', label: 'Dynamic Agents', icon: Bot },
  { href: '#capabilities', label: 'Building Capabilities', icon: Component },
  { href: '#example-use-cases', label: 'Example Use Cases', icon: Lightbulb },
  { href: '#mcp-methods', label: 'MCP Methods', icon: BrainCircuit },
  { href: '#available-tools', label: 'Available Tools', icon: ListTree },
  { href: '#python-example', label: 'Python Example', icon: Puzzle },
  { href: '#advanced-python-example', label: 'Advanced Example', icon: Puzzle },
  { href: '#curl-example', label: 'cURL Example', icon: Terminal },
];

// Modal for displaying the diagram
const DiagramModal = ({ chart, onClose }: { chart: string; onClose: () => void }) => {
  useEffect(() => {
    const handleEsc = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleEsc);
    return () => {
      window.removeEventListener('keydown', handleEsc);
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 sm:p-6 md:p-8"
      onClick={onClose}
    >
      <div
        className="bg-slate-950 p-6 sm:p-8 rounded-xl border border-slate-700 max-w-6xl w-full max-h-full overflow-auto shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="h-full w-full">
          <MermaidDiagram chart={chart} />
        </div>
      </div>
    </div>
  );
};

const ApiDocsPage = () => {
  const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://jean-memory-api.onrender.com";
  const [isDiagramModalOpen, setIsDiagramModalOpen] = useState(false);

  const novellaTitle = "The Irreverent Journey: A Life in Progress";
  const novellaDescription = `I've crafted a biographical novela based on the deep analysis of your memories and documents. The story traces your journey from a questioning child in the Midwest through your current work building Jean and exploring AI personalization.

The narrative captures key themes that emerged from your memories:

- Your natural "psychological reactance" to arbitrary rules and authority
- The evolution from banking to entrepreneurship via the "zero plan" leap in June 2024
- Your breakthrough insight about "General Personal Embeddings" and AI understanding human complexity
- The systematic, technical approach you take to building (evidenced by your memory tools testing)
- The philosophical framework of "irreverence" as a creative force
- Your current work on Jean, the personal memory layer, and Model Context Protocol

The novela is structured as a journey of becoming - someone learning to trust their instincts, build their own path, and create technology that serves human complexity rather than reducing it. It weaves together the technical, personal, and philosophical threads that define your approach to life and work.

The tone balances the introspective quality of your essays with the practical energy of your entrepreneurial ventures, ending with the understanding that this is very much a story in progress - you're still building, still exploring, still following that inner "blue note" wherever it leads.`;

  const architectureDiagram = `
graph TD
    subgraph "Unified Jean Memory API Architecture"
        A["UI Request<br/>(jeanmemory.com)"] --> B{JWT in Header};
        C["Claude Desktop Request"] --> D{"x-user-id + x-client-name<br/>Headers"};
        E["API Key Request<br/>(Programmatic)"] --> F{"X-Api-Key Header<br/>'jean_sk_...'"};

        B --> G["GET /api/v1/*<br/>(UI Endpoints)"];
        D --> H["POST /mcp/messages/<br/>(Unified MCP Endpoint)"];
        F --> H;
        
        G -- "Uses get_current_supa_user" --> I["✅ UI Validated"];
        H -- "Dual-path authentication:<br/>1. API Key → get_user_from_api_key_header<br/>2. Headers → existing validation" --> J["✅ MCP Validated"];
        
        J --> K["Execute Memory Tools<br/>(ask_memory, add_memories, etc.)"];
    end

    subgraph "Memory Tools Registry"
        K --> L["ask_memory"];
        K --> M["add_memories"];
        K --> N["search_memory"];
        K --> O["list_memories"];
        K --> P["deep_memory_query"];
    end
    
    classDef ui fill:#166534,stroke:#4ade80,color:#fafafa,stroke-width:1px
    classDef unified fill:#172554,stroke:#60a5fa,color:#fafafa,stroke-width:1px
    classDef tools fill:#7c2d12,stroke:#fb923c,color:#fafafa,stroke-width:1px
    classDef validated fill:#166534,stroke:#4ade80,color:#fafafa,stroke-width:1px
    
    class A,B,G ui
    class C,D,E,F,H unified
    class I,J validated
    class K,L,M,N,O,P tools
  `;

  return (
    <DocsLayout navItems={navItems}>
      <section id="introduction">
        <h1 className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-pink-500 mb-4">Jean Memory API Documentation</h1>
        <p className="text-lg text-slate-400 mb-4">
          The Jean Memory API provides a robust, unified memory layer for your AI applications. Built on the Model Context Protocol (MCP), it offers secure API key authentication for programmatic access while maintaining full compatibility with existing Claude Desktop integrations.
        </p>
        <div className="flex items-center gap-4 p-4 bg-emerald-900/30 border border-emerald-700/50 rounded-lg">
          <div className="w-3 h-3 bg-emerald-400 rounded-full animate-pulse"></div>
          <p className="text-emerald-200 text-sm">
            <strong>Production Ready:</strong> Zero breaking changes, dual-path authentication, and enterprise-grade security.
          </p>
        </div>
      </section>

      <section id="authentication">
        <h2 className="text-3xl font-bold text-slate-100 mb-4 flex items-center"><Shield className="w-7 h-7 mr-3 text-purple-400"/>Authentication</h2>
        <p className="text-slate-400 mb-4">
          The API supports dual-path authentication for maximum flexibility and compatibility. You can authenticate using either API keys (recommended for programmatic access) or the existing header-based system (used by Claude Desktop).
        </p>
        <div className="space-y-6">
          <div className="p-4 border border-emerald-700/80 bg-emerald-900/50 rounded-lg">
            <h3 className="font-semibold text-emerald-200 text-lg flex items-center mb-3"><Key className="w-5 h-5 mr-2"/>Option 1: API Key Authentication (Recommended)</h3>
            <div className="space-y-3">
              <div>
                <h4 className="font-medium text-emerald-100">Step 1: Generate an API Key</h4>
                <p className="text-emerald-200/80 text-sm mt-1">
                  Navigate to your <a href="/dashboard-new" className="text-emerald-300 underline hover:text-emerald-200">Dashboard</a> → Settings → API Keys to generate a new key.
                </p>
              </div>
              <div>
                <h4 className="font-medium text-emerald-100">Step 2: Use X-Api-Key Header</h4>
                <p className="text-emerald-200/80 text-sm mt-1">
                  Include your API key in the <code className="font-mono text-xs bg-emerald-800/50 px-1 rounded">X-Api-Key</code> header:
                </p>
                <CodeBlock lang="http" code={`X-Api-Key: jean_sk_s8ad0fI7x2VD2KnyLewH0e3ajuRV_1mdWGgnsBJ6VA8`} />
              </div>
            </div>
          </div>
          <div className="p-4 border border-slate-700/80 bg-slate-900/50 rounded-lg">
            <h3 className="font-semibold text-slate-200 text-lg flex items-center mb-3"><Code className="w-5 h-5 mr-2"/>Option 2: Header-Based Authentication</h3>
            <p className="text-slate-400 text-sm">
              This is used internally by Claude Desktop and the UI. Requires both <code className="font-mono text-xs">x-user-id</code> and <code className="font-mono text-xs">x-client-name</code> headers.
            </p>
            <CodeBlock lang="http" code={`x-user-id: your-supabase-user-id
x-client-name: your-app-name`} />
          </div>
        </div>
      </section>

      <section id="endpoints">
        <h2 className="text-3xl font-bold text-slate-100 mb-4 flex items-center"><GitBranch className="w-7 h-7 mr-3 text-purple-400"/>Unified API Endpoint</h2>
        <p className="text-slate-400 mb-4">
          All interactions use a single, unified MCP endpoint that supports both API key authentication (for programmatic access) and header-based authentication (for existing Claude/UI integrations). This endpoint accepts POST requests with standard JSON-RPC 2.0 payloads.
        </p>
        <div className="flex items-center gap-2 mt-3">
          <span className="font-mono text-xs font-bold text-green-400 bg-green-900/50 px-2 py-1 rounded">POST</span>
          <span className="font-mono text-sm text-slate-300">{API_URL}/mcp/messages/</span>
        </div>
        <Alert className="border-sky-700/80 bg-sky-900/50 rounded-lg text-sky-200 text-sm mt-4">
          <p>
            <strong>Zero Breaking Changes:</strong> This unified endpoint maintains full compatibility with existing Claude Desktop and UI integrations while adding secure API key support for programmatic access.
          </p>
        </Alert>
      </section>
      
      <section id="dynamic-agents">
        <h2 className="text-3xl font-bold text-slate-100 mb-4 flex items-center"><Bot className="w-7 h-7 mr-3 text-purple-400"/>Building Dynamic Agents</h2>
        <p className="text-slate-400 mb-4">
          The Jean Memory Agent API is not designed for static, hardcoded calls. It is built to be used as a dynamic tool provider (MCP) within an LLM application, allowing you to create agents that can reason and decide when to access memory.
        </p>
        <div className="space-y-4">
          <div>
            <h3 className="font-semibold text-slate-200 text-lg">The Agentic Loop</h3>
            <p className="text-slate-400 mt-1">
              The core workflow involves prompting your LLM with the available tools. The LLM then dynamically generates a JSON-RPC payload to call a tool based on the conversational context. Your application executes this call and feeds the result back to the LLM.
            </p>
          </div>
          <div className="p-4 border border-teal-700/80 bg-teal-900/50 rounded-lg text-teal-300 text-sm">
            This architecture enables your agent to intelligently decide when to add a new memory using <code className="font-mono text-sm">add_memories</code> or retrieve context using <code className="font-mono text-sm">search_memories</code>.
          </div>
        </div>
      </section>

      <section id="capabilities">
        <h2 className="text-3xl font-bold text-slate-100 mb-4 flex items-center"><Component className="w-7 h-7 mr-3 text-purple-400"/>Building Capabilities: Tools vs. Workflows</h2>
        <p className="text-slate-400 mb-4">
          A critical concept for building advanced agents is understanding the difference between the foundational tools provided by the API and the complex capabilities you can build with them.
        </p>
        <Alert className="border-sky-700/80 bg-sky-900/50 rounded-lg text-sky-200 text-sm mb-6">
          <p>
            Capabilities like "asking a question of your memory" (i.e., `ask_memory`) are not single tools. They are **emergent workflows** that an agent executes by chaining the foundational tools together.
          </p>
        </Alert>
        <div className="space-y-4">
          <div>
            <h3 className="font-semibold text-slate-200 text-lg">Example: How an Agent "Asks Memory"</h3>
            <p className="text-slate-400 mt-1 mb-4">
              The API does not have a single `ask_memory` tool. Here's how an agent performs that capability using the real tools:
            </p>
            <div className="bg-slate-800/50 p-4 rounded text-sm">
               <ol className="list-decimal list-inside space-y-3 text-slate-300">
                <li>
                  <strong>User Asks:</strong> "What is my relationship with Project Phoenix?"
                </li>
                <li>
                  <strong>Agent Plans:</strong> The LLM powering the agent deconstructs the request. It forms a plan: "The user wants relationships. I will query the knowledge graph for the 'Project Phoenix' node."
                </li>
                <li>
                  <strong>Agent Executes Foundational Tools:</strong> The agent makes one or more calls to the tools you have, like `search_memories` or a direct graph query.
                </li>
                <li>
                  <strong>Agent Receives Structured Data:</strong> The API returns raw data, e.g., `[(User, IS_LEAD_ON, Project Phoenix), (Project Phoenix, USES_TECHNOLOGY, Python)]`.
                </li>
                <li>
                  <strong>Agent Synthesizes Answer:</strong> The LLM receives this structured data and formulates a human-readable response: "You are the lead on Project Phoenix, which uses Python."
                </li>
              </ol>
            </div>
             <p className="text-slate-400 mt-4 text-sm">
              This architecture is intentional. It provides you with the powerful, low-level building blocks (`add_memories`, `add_graph_memory`, etc.) to create your own custom, sophisticated reasoning workflows, rather than limiting you to a few predefined capabilities.
            </p>
          </div>
        </div>
      </section>

      <section id="example-use-cases">
        <h2 className="text-3xl font-bold text-slate-100 mb-4 flex items-center"><Lightbulb className="w-7 h-7 mr-3 text-purple-400"/>Example Use Cases</h2>
        <p className="text-slate-400 mb-6">
          The Jean Memory API is versatile. By giving your agents a reliable memory, you can unlock a wide range of powerful applications. Here are a few examples to inspire you.
        </p>
        <div className="space-y-8">

          {/* Programmatic Content Creation */}
          <div className="p-6 border border-slate-700/50 rounded-lg bg-slate-900/40">
            <h3 className="text-lg font-semibold text-teal-400 mb-2">Programmatic Content Creation</h3>
            <p className="text-slate-400 mb-4">
              Create agents that act as writing assistants, maintaining a consistent voice, style, and context across numerous documents. The agent can remember key arguments from past essays, a user's specific tone, or technical details about a project.
            </p>
            <div className="bg-slate-800/50 p-3 rounded text-sm">
              <strong className="text-slate-300">Example Flow:</strong>
              <ol className="list-decimal list-inside mt-2 space-y-1 text-slate-400">
                <li>User: "Remember my startup is called 'InnovateAI' and it uses a custom reinforcement learning model."</li>
                <li>Agent: (Calls <code className="font-mono text-xs">add_memories</code>) "Got it."</li>
                <li>User: "Help me draft an investor update email."</li>
                <li>Agent: (Calls <code className="font-mono text-xs">search_memories</code> for project details) "Of course. Here is a draft for 'InnovateAI' that highlights your unique RL model..."</li>
              </ol>
            </div>
          </div>

          {/* Personal Digital Assistant */}
          <div className="p-6 border border-slate-700/50 rounded-lg bg-slate-900/40">
            <h3 className="text-lg font-semibold text-teal-400 mb-2">Personal Digital Assistant</h3>
            <p className="text-slate-400 mb-4">
              Build a truly personal agent that understands a user's life. By remembering personal preferences, important relationships, career goals, and even inside jokes, the agent can provide deeply contextual assistance, manage schedules, and act on the user's behalf with genuine understanding.
            </p>
             <div className="bg-slate-800/50 p-3 rounded text-sm">
              <strong className="text-slate-300">Example Flow:</strong>
              <ol className="list-decimal list-inside mt-2 space-y-1 text-slate-400">
                <li>User: "My wife's name is Sarah and her birthday is March 15th. Remind me a week before."</li>
                <li>Agent: (Calls <code className="font-mono text-xs">add_memories</code>) "I'll remember that for you."</li>
                <li>(A week before March 15th) User: "What's on my plate this week?"</li>
                <li>Agent: (Calls <code className="font-mono text-xs">search_memories</code>) "You have your usual meetings, and a reminder that Sarah's birthday is next week. Would you like help finding a gift based on your past conversations about her interests?"</li>
              </ol>
            </div>
          </div>

          {/* Corporate Knowledge Agent */}
          <div className="p-6 border border-slate-700/50 rounded-lg bg-slate-900/40">
            <h3 className="text-lg font-semibold text-teal-400 mb-2">Corporate Knowledge Agent</h3>
            <p className="text-slate-400 mb-4">
              Deploy agents within a company that have a secure, shared memory of internal knowledge. This can include project histories, technical documentation, team roles, and meeting summaries. This is perfect for onboarding new employees or answering complex questions that would normally require interrupting a senior developer.
            </p>
             <div className="bg-slate-800/50 p-3 rounded text-sm">
              <strong className="text-slate-300">Example Flow:</strong>
              <ol className="list-decimal list-inside mt-2 space-y-1 text-slate-400">
                <li>(Admin): Uploads all of Q1 project documentation into the agent's memory.</li>
                <li>New Employee: "What was the main outcome of the 'Project Phoenix' initiative last quarter?"</li>
                <li>Agent: (Calls <code className="font-mono text-xs">search_memories</code>) "Project Phoenix concluded with the successful deployment of the new user authentication service, which reduced login times by 40%. The project lead was Alice."</li>
              </ol>
            </div>
          </div>

          {/* Hyper-Personalized Content Generation */}
          <div className="p-6 border border-slate-700/50 rounded-lg bg-slate-900/40">
            <h3 className="text-lg font-semibold text-teal-400 mb-2">Hyper-Personalized Content Generation</h3>
            <p className="text-slate-400 mb-4">
              While the API does not expose a single "deep query" tool, you can build advanced agents that perform deep analysis by creating an **emergent workflow**. This involves chaining the available foundational tools to analyze a large corpus of documents and generate rich, biographical content.
            </p>
            <Alert>
              <AlertTitle className="flex items-center gap-2"><Lightbulb className="w-4 h-4" />Advanced Workflow Example</AlertTitle>
              <AlertDescription>
                This is not a single tool call. It is a sophisticated agent workflow that you build in your own application:
                <ol className="list-decimal list-inside mt-2 space-y-1">
                  <li><strong>Ingest Documents:</strong> Use a tool like `sync_substack` or `chunk_documents` to load the user's writings (e.g., 2 million tokens across 20+ documents) into the memory system.</li>
                  <li><strong>Iterative Search:</strong> The agent makes a series of targeted `search_memories` calls to extract key themes. For example: `search_memories(query="early career motivations")` followed by `search_memories(query="perspectives on AI ethics")`.</li>
                  <li><strong>Synthesize Narrative:</strong> The agent's controlling LLM takes the structured data from all search results and synthesizes it into a coherent, human-readable narrative, like the novella example below.</li>
                </ol>
              </AlertDescription>
            </Alert>
            <div className="mt-4 bg-slate-800/50 p-4 rounded text-sm">
              <h4 className="font-bold text-slate-200 text-base mb-2">{novellaTitle}</h4>
              <p className="text-slate-300 whitespace-pre-wrap">{novellaDescription}</p>
            </div>
          </div>

          {/* Agentic Coding: A Cross-Application Workflow */}
          <div className="p-6 border border-slate-700/50 rounded-lg bg-slate-900/40">
            <h3 className="text-lg font-semibold text-teal-400 mb-2 flex items-center gap-2">
              <Share2 className="w-5 h-5" />
              Agentic Coding: A Cross-Application Workflow
            </h3>
            <p className="text-slate-400 mb-4">
              Orchestrate a swarm of specialized agents that collaborate across different applications, using a shared memory context to automate complex developer workflows.
            </p>
             <div className="bg-slate-800/50 p-3 rounded text-sm">
              <strong className="text-slate-300">Example Flow:</strong>
              <ol className="list-decimal list-inside mt-2 space-y-2 text-slate-400">
                <li>
                  <strong>A user reports a bug in Slack:</strong><br/>
                  A 'Slack Monitor' agent sees the message. It calls <code className="font-mono text-xs">add_memories</code> with the bug report, `source_app: 'slack'`, and `metadata: &lbrace;'status': 'reported'&rbrace;`.
                </li>
                <li>
                  <strong>A 'Jira Agent' springs into action:</strong><br/>
                  This agent periodically searches for memories where `source_app: 'slack'` and `metadata.status: 'reported'`. It finds the new bug, creates a Jira ticket, then calls <code className="font-mono text-xs">add_memories</code> with the Jira ticket info, `source_app: 'jira'`, and links it to the original Slack memory.
                </li>
                <li>
                  <strong>A developer asks for context:</strong><br/>
                  A 'Developer Assistant' agent in the IDE is asked, "What's the context on ticket JIRA-123?". It calls <code className="font-mono text-xs">search_memories</code> for "JIRA-123", finds both the Jira and Slack memories, and provides the full history, including the original user conversation.
                </li>
                 <li>
                  <strong>The agent automates a PR:</strong><br/>
                  After the fix is committed, the Developer Assistant agent creates a pull request, using the shared memory to automatically populate the PR description with the details from both the Jira ticket and the original Slack conversation.
                </li>
              </ol>
            </div>
          </div>

        </div>
      </section>

      <section id="mcp-methods">
          <h2 className="text-3xl font-bold text-slate-100 mb-4 flex items-center"><BrainCircuit className="w-7 h-7 mr-3 text-purple-400"/>MCP Methods</h2>
          <p className="text-slate-400 mb-4">
            The agent endpoint supports all standard MCP methods, including tool calls. You can interact with the memory system using methods like <code className="font-mono text-sm">tools/list</code>, <code className="font-mono text-sm">resources/list</code>, and <code className="font-mono text-sm">tools/call</code>.
          </p>
          <div className="p-4 border border-sky-700/80 bg-sky-900/50 rounded-lg text-sky-300 text-sm">
              The architecture has been unified. The agent endpoint is a fully-featured MCP server, providing the same capabilities as the internal system used by Claude.
              <br/><br/>
              The public API provides access to the core, high-performance tools like <code className="font-mono text-sm">add_memories</code> and <code className="font-mono text-sm">search_memories</code>. More resource-intensive analytical tools, such as those for processing entire documents, remain internal to ensure speed and reliability for all agents.
          </div>
      </section>

      <section id="available-tools">
        <h2 className="text-3xl font-bold text-slate-100 mb-4 flex items-center"><ListTree className="w-7 h-7 mr-3 text-purple-400"/>Available Tools</h2>
        <p className="text-slate-400 mb-6">
          The unified API exposes powerful tools to interact with user memory. These are the core, high-performance tools available via the <code className="font-mono text-sm">tools/call</code> MCP method.
        </p>
        <div className="space-y-8">
          {/* ask_memory tool */}
          <div className="p-6 border border-slate-700/50 rounded-lg bg-slate-900/40">
            <h3 className="font-mono text-lg text-pink-400 mb-2">ask_memory</h3>
            <p className="text-slate-400 mb-4">
              <strong>FAST memory search</strong> that provides conversational answers in under 5 seconds. Perfect for most questions - try this FIRST before using heavier tools. Searches stored memories only (not full documents).
            </p>
            <h4 className="font-semibold text-slate-200 mb-2">Input Schema:</h4>
            <CodeBlock lang="json" code={JSON.stringify({
              question: {
                type: "string",
                description: "Any natural language question about the user's memories, thoughts, documents, or experiences"
              }
            }, null, 2)} />
            <h4 className="font-semibold text-slate-200 mt-4 mb-2">Example Payload:</h4>
            <CodeBlock lang="json" code={JSON.stringify({
              jsonrpc: "2.0",
              method: "tools/call",
              params: {
                name: "ask_memory",
                arguments: {
                  question: "What are my preferences for coding languages?"
                }
              },
              id: 1
            }, null, 2)} />
          </div>

          {/* add_memories tool */}
          <div className="p-6 border border-slate-700/50 rounded-lg bg-slate-900/40">
            <h3 className="font-mono text-lg text-pink-400 mb-2">add_memories</h3>
            <p className="text-slate-400 mb-4">
              Store important information, preferences, facts, and observations about the user. Use this to remember key details learned during conversation, user preferences, values, beliefs, or anything the user wants remembered for future conversations.
            </p>
            <h4 className="font-semibold text-slate-200 mb-2">Input Schema:</h4>
            <CodeBlock lang="json" code={JSON.stringify({
              text: {
                type: "string",
                description: "Important information to remember about the user (facts, preferences, insights, observations, etc.)"
              }
            }, null, 2)} />
            <h4 className="font-semibold text-slate-200 mt-4 mb-2">Example Payload:</h4>
            <CodeBlock lang="json" code={JSON.stringify({
              jsonrpc: "2.0",
              method: "tools/call",
              params: {
                name: "add_memories",
                arguments: {
                  text: "User prefers TypeScript over JavaScript for new projects and likes to use strict type checking."
                }
              },
              id: 2
            }, null, 2)} />
          </div>

          {/* search_memory tool */}
          <div className="p-6 border border-slate-700/50 rounded-lg bg-slate-900/40">
            <h3 className="font-mono text-lg text-pink-400 mb-2">search_memory</h3>
            <p className="text-slate-400 mb-4">
              Quick keyword-based search through the user's memories. Perfect for finding specific facts, dates, names, or simple queries. Use when you need raw memory data rather than a conversational response.
            </p>
            <h4 className="font-semibold text-slate-200 mb-2">Input Schema:</h4>
            <CodeBlock lang="json" code={JSON.stringify({
              query: {
                type: "string",
                description: "Keywords or phrases to search for"
              },
              limit: {
                type: "integer",
                description: "Maximum number of results to return (default: 10)"
              }
            }, null, 2)} />
            <h4 className="font-semibold text-slate-200 mt-4 mb-2">Example Payload:</h4>
            <CodeBlock lang="json" code={JSON.stringify({
              jsonrpc: "2.0",
              method: "tools/call",
              params: {
                name: "search_memory",
                arguments: {
                  query: "TypeScript preferences",
                  limit: 5
                }
              },
              id: 3
            }, null, 2)} />
          </div>

          {/* list_memories tool */}
          <div className="p-6 border border-slate-700/50 rounded-lg bg-slate-900/40">
            <h3 className="font-mono text-lg text-pink-400 mb-2">list_memories</h3>
            <p className="text-slate-400 mb-4">
              Browse through the user's stored memories to get an overview of what you know about them. Returns raw memory data without analysis - good for getting oriented or checking what's stored.
            </p>
            <h4 className="font-semibold text-slate-200 mb-2">Input Schema:</h4>
            <CodeBlock lang="json" code={JSON.stringify({
              limit: {
                type: "integer",
                description: "Maximum number of memories to show (default: 20)"
              }
            }, null, 2)} />
            <h4 className="font-semibold text-slate-200 mt-4 mb-2">Example Payload:</h4>
            <CodeBlock lang="json" code={JSON.stringify({
              jsonrpc: "2.0",
              method: "tools/call",
              params: {
                name: "list_memories",
                arguments: {
                  limit: 10
                }
              },
              id: 4
            }, null, 2)} />
          </div>

          {/* deep_memory_query tool */}
          <div className="p-6 border border-slate-700/50 rounded-lg bg-slate-900/40">
            <h3 className="font-mono text-lg text-pink-400 mb-2">deep_memory_query</h3>
            <p className="text-slate-400 mb-4">
              <strong>COMPREHENSIVE search</strong> that analyzes ALL user content including full documents and essays. Takes 30-60 seconds and processes everything. Use sparingly for complex questions that require analyzing entire documents or finding patterns across multiple sources.
            </p>
            <h4 className="font-semibold text-slate-200 mb-2">Input Schema:</h4>
            <CodeBlock lang="json" code={JSON.stringify({
              search_query: {
                type: "string",
                description: "Complex question or analysis request"
              },
              memory_limit: {
                type: "integer",
                description: "Number of memories to include (default: 10)"
              },
              chunk_limit: {
                type: "integer", 
                description: "Number of document chunks to include (default: 10)"
              },
              include_full_docs: {
                type: "boolean",
                description: "Whether to include complete documents (default: true)"
              }
            }, null, 2)} />
            <h4 className="font-semibold text-slate-200 mt-4 mb-2">Example Payload:</h4>
            <CodeBlock lang="json" code={JSON.stringify({
              jsonrpc: "2.0",
              method: "tools/call",
              params: {
                name: "deep_memory_query",
                arguments: {
                  search_query: "Analyze my writing style and key themes across all my essays"
                }
              },
              id: 5
            }, null, 2)} />
          </div>

        </div>
      </section>

      <section id="python-example">
        <h2 className="text-3xl font-bold text-slate-100 mb-4 flex items-center"><Puzzle className="w-7 h-7 mr-3 text-purple-400"/>Python Example</h2>
        <p className="text-slate-400 mb-4">
          Here is a simple example of how to use the unified API with Python's <code className="font-mono text-sm">requests</code> library to add a new memory.
        </p>
        <CodeBlock lang="python" code={`
import requests
import json
import os

# Load your API key from environment variable
API_KEY = os.environ.get("JEAN_API_KEY")
API_URL = "${API_URL}/mcp/messages/"

if not API_KEY:
    raise ValueError("JEAN_API_KEY environment variable not set!")

headers = {
    "X-Api-Key": API_KEY,
    "Content-Type": "application/json"
}

payload = {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "add_memories",
        "arguments": {
            "text": "The user is interested in learning about generative adversarial networks (GANs) and prefers Python for machine learning projects."
        }
    },
    "id": 1
}

try:
    response = requests.post(API_URL, headers=headers, data=json.dumps(payload))
    response.raise_for_status()  # Raises an exception for bad status codes
    
    result = response.json()
    print("Response:", result)
    
    # Extract the actual response text
    if "result" in result and "content" in result["result"]:
        for content in result["result"]["content"]:
            if content["type"] == "text":
                print("Memory added:", content["text"])

except requests.exceptions.RequestException as e:
    print(f"An error occurred: {e}")
        `} />
        <p className="text-slate-400 mt-4">
          A successful call to <code className="font-mono text-sm">add_memories</code> will return a detailed confirmation:
        </p>
        <CodeBlock lang="json" code={`
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Successfully added 2 new memory(ies). Total time: 4.82s. Content: The user is interested in learning about..."
      }
    ]
  }
}
`} />
      </section>

      <section id="advanced-python-example">
        <h2 className="text-3xl font-bold text-slate-100 mb-4 flex items-center"><Puzzle className="w-7 h-7 mr-3 text-purple-400"/>Advanced Python Example</h2>
        <p className="text-slate-400 mb-4">
          This example demonstrates a more complex, realistic workflow where an agent uses shared memory to answer a question that requires context from multiple applications (Slack and Jira).
        </p>
        <CodeBlock lang="python" code={`
import requests
import json
import os

API_KEY = os.environ.get("JEAN_API_KEY")
API_URL = "${API_URL}/mcp/messages/"

def call_jean_api(payload):
    """Helper function to call the Jean Memory API."""
    if not API_KEY:
        raise ValueError("JEAN_API_KEY environment variable not set!")
    
    headers = {
        "X-Api-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(API_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API call failed: {e}")
        return None

# --- Step 1: An agent adds memories from different sources ---

# A 'Slack Monitor' agent captures a user report
print("Step 1: Ingesting memories from Slack and Jira...")
slack_payload = {
    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
    "params": {
        "name": "add_memories",
        "arguments": {
            "text": "User 'dave' reported in #bugs: 'Can't reset my password, the link is broken.'",
            "source_app": "slack",
            "metadata": {"channel": "#bugs", "status": "reported"}
        }
    }
}
call_jean_api(slack_payload)

# A 'Jira Monitor' agent sees a new ticket is created
jira_payload = {
    "jsonrpc": "2.0", "id": 2, "method": "tools/call",
    "params": {
        "name": "add_memories",
        "arguments": {
            "text": "Jira Ticket JIRA-123 created: 'Password reset link broken'",
            "source_app": "jira",
            "metadata": {"ticket_id": "JIRA-123", "status": "open"}
        }
    }
}
call_jean_api(jira_payload)
print("Memories added.")

# --- Step 2: A developer's agent seeks context ---

print("\\nStep 2: A developer asks for context on a Jira ticket.")
dev_question = "What's the full context for ticket JIRA-123?"

# --- Step 3: The agent plans and executes a search ---

# The agent's LLM would determine it needs to search for the ticket ID
# across all relevant applications.
print("Step 3: Agent searching for 'JIRA-123' across Slack and Jira...")
search_payload = {
    "jsonrpc": "2.0", "id": 3, "method": "tools/call",
    "params": {
        "name": "search_memories",
        "arguments": {
            "query": "JIRA-123",
            "source_app": "slack,jira" # Filter search to specific apps
        }
    }
}
search_results = call_jean_api(search_payload)

# --- Step 4: The agent synthesizes the results ---

print("\\nStep 4: Agent synthesizes a response from the search results.")
if search_results and search_results.get('result', {}).get('results'):
    context = ""
    for res in search_results['result']['results']:
        context += f"- {res['text']} (Source: {res['metadata'].get('source_app', 'N/A')})\\n"
    
    final_answer = f"""
Here is the context for ticket JIRA-123:

{context}
This allows you to see the original user report from Slack alongside the formal Jira ticket.
"""
    print(final_answer)
else:
    print("Could not find any context for that ticket.")

        `} />
      </section>

      <section id="curl-example">
        <h2 className="text-3xl font-bold text-slate-100 mb-4 flex items-center"><Terminal className="w-7 h-7 mr-3 text-purple-400"/>cURL Example</h2>
        <p className="text-slate-400 mb-4">
          You can also interact with the API directly from your terminal using cURL. This example lists the available tools.
        </p>
        <CodeBlock lang="bash" code={`
curl -X POST ${API_URL}/mcp/messages/ \\
  -H "X-Api-Key: YOUR_JEAN_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "params": {},
    "id": 1
  }'
        `} />
        <p className="text-slate-400 mt-4">
          A successful request will return a JSON object with a list of available tools:
        </p>
        <CodeBlock lang="json" code={`
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "add_memories",
        "description": "Add one or more memories. The input is a list of strings, where each string is a memory.",
        "input_schema": {
          "type": "object",
          "properties": {
            "text": {
              "type": "string",
              "description": "The memory text to add. For multiple, use a newline-separated string."
            }
          },
          "required": ["text"]
        }
      },
      {
        "name": "search_memories",
        "description": "Searches for memories based on a query string.",
        "input_schema": {
          "type": "object",
          "properties": {
            "query": {
              "type": "string",
              "description": "The query to search for."
            }
          },
          "required": ["query"]
        }
      }
    ]
  }
}
`} />
      </section>

      <section id="quick-test">
        <h2 className="text-3xl font-bold text-slate-100 mb-4 flex items-center"><Terminal className="w-7 h-7 mr-3 text-purple-400"/>Quick Test</h2>
        <p className="text-slate-400 mb-4">
          Verify your API key is working with this simple test. Replace <code className="font-mono text-sm">YOUR_API_KEY</code> with your actual key from the dashboard.
        </p>
        <CodeBlock lang="bash" code={`
# Test API connection
curl -X POST ${API_URL}/mcp/messages/ \\
  -H "X-Api-Key: YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {},
    "id": 1
  }'

# Expected response: {"jsonrpc":"2.0","result":{"protocolVersion":"2024-11-05",...},"id":1}
        `} />
        <div className="mt-4 p-4 bg-sky-900/30 border border-sky-700/50 rounded-lg">
          <p className="text-sky-200 text-sm">
            <strong>💡 Success indicators:</strong> A successful response includes <code className="font-mono text-xs">protocolVersion</code> and <code className="font-mono text-xs">serverInfo</code>. If you get an authentication error, double-check your API key format and ensure it starts with <code className="font-mono text-xs">jean_sk_</code>.
          </p>
        </div>
      </section>
      
      <section id="architecture-diagram">
          <h2 className="text-3xl font-bold text-slate-100 mb-4 flex items-center"><Server className="w-7 h-7 mr-3 text-purple-400"/>Unified Architecture</h2>
          <p className="text-slate-400 mb-4">
            Our implementation uses a <strong>unified endpoint architecture</strong> that maintains 100% compatibility with existing integrations while adding secure API key support. The single <code className="font-mono text-sm">/mcp/messages/</code> endpoint handles all memory operations through dual-path authentication.
            <span className="block text-sm text-slate-500 mt-1">Click the diagram to expand.</span>
          </p>
          <Alert className="border-emerald-700/80 bg-emerald-900/50 rounded-lg text-emerald-200 text-sm mb-6">
            <p>
              <strong>Zero Breaking Changes:</strong> Existing Claude Desktop configurations and UI integrations continue to work exactly as before. The new API key authentication is additive, not replacing existing functionality.
            </p>
          </Alert>
          <div className="cursor-zoom-in" onClick={() => setIsDiagramModalOpen(true)}>
            <MermaidDiagram chart={architectureDiagram} />
          </div>

          {isDiagramModalOpen && (
            <DiagramModal chart={architectureDiagram} onClose={() => setIsDiagramModalOpen(false)} />
          )}
      </section>

    </DocsLayout>
  );
};

export default ApiDocsPage; 