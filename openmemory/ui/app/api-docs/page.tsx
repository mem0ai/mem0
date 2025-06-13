"use client";

import React, { useState, useEffect, useRef } from 'react';
import { GitBranch, Shield, BookOpen, Puzzle, Terminal, Code, Server, Key, BrainCircuit, Copy, Check, LucideIcon, ListTree } from 'lucide-react';
import { usePathname, useRouter } from 'next/navigation';

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
  { href: '#mcp-methods', label: 'MCP Methods', icon: BrainCircuit },
  { href: '#available-tools', label: 'Available Tools', icon: ListTree },
  { href: '#python-example', label: 'Python Example', icon: Puzzle },
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

  const architectureDiagram = `
graph TD
    subgraph "Existing Production Auth (Unchanged & Safe)"
        A["UI Request<br/>(jeanmemory.com)"] --> B{JWT in Header};
        C["Claude 'supergateway' Request"] --> D{"x-user-id" in Header};

        B --> E["GET /api/v1/*"];
        D --> F["POST /mcp/messages/"];
        
        E -- "Uses get_current_supa_user" --> G["✅ Validated"];
        F -- "Uses main MCP handler" --> G;
    end

    subgraph "New Agent API (Isolated System)"
        H["Agent Request"] --> I{"API Key<br/>'jean_sk_...' in Header"};
        I --> J["POST /agent/v1/mcp/messages/"];
        J -- "Uses get_current_agent" --> K["✅ Validated"];
        K -- "Forwards to main MCP handler" --> F;
    end
    
    classDef existing fill:#18181b,stroke:#a1a1aa,color:#fafafa,stroke-width:1px
    classDef new fill:#172554,stroke:#60a5fa,color:#fafafa,stroke-width:1px
    classDef validated fill:#166534,stroke:#4ade80,color:#fafafa,stroke-width:1px
    
    class A,B,C,D,E,F existing
    class H,I,J new
    class G,K validated
  `;

  return (
    <DocsLayout navItems={navItems}>
      <section id="introduction">
        <h1 className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-pink-500 mb-4">Agent API Documentation</h1>
        <p className="text-lg text-slate-400">
          The Jean Memory Agent API provides a robust, isolated, and easy-to-use memory layer for your AI applications. It's designed for production use cases where multiple AI agents or services need to interact with a user's memory store via a secure, key-based authentication system.
        </p>
      </section>

      <section id="authentication">
        <h2 className="text-3xl font-bold text-slate-100 mb-4 flex items-center"><Shield className="w-7 h-7 mr-3 text-purple-400"/>Authentication</h2>
        <p className="text-slate-400 mb-4">
          All agent endpoints are protected and require an API key. Keys are generated from the Jean Memory UI and must be passed in the <code className="font-mono text-sm">Authorization</code> header as a Bearer token.
        </p>
        <div className="space-y-4">
          <div>
            <h3 className="font-semibold text-slate-200 text-lg flex items-center"><Key className="w-5 h-5 mr-2 text-slate-400"/>Step 1: Generate an API Key</h3>
            <p className="text-slate-400 mt-1">
              Navigate to the <a href="/settings" className="text-purple-400 underline hover:text-purple-300">Settings page</a> in the Jean Memory dashboard. From there, you can generate, view, and revoke API keys.
            </p>
          </div>
          <div>
            <h3 className="font-semibold text-slate-200 text-lg flex items-center"><Code className="w-5 h-5 mr-2 text-slate-400"/>Step 2: Use the API Key</h3>
            <p className="text-slate-400 mt-1">
              When making a request to the agent API, include your key in the <code className="font-mono text-sm">Authorization</code> header. The key must be prefixed with <code className="font-mono text-sm">Bearer </code>.
            </p>
            <CodeBlock lang="http" code={`Authorization: Bearer jean_sk_...`} />
          </div>
        </div>
      </section>

      <section id="endpoints">
        <h2 className="text-3xl font-bold text-slate-100 mb-4 flex items-center"><GitBranch className="w-7 h-7 mr-3 text-purple-400"/>API Endpoint</h2>
        <p className="text-slate-400 mb-4">
          All agent-based interactions use a single, unified MCP endpoint. This endpoint accepts POST requests with a standard JSON-RPC 2.0 payload.
        </p>
        <div className="flex items-center gap-2 mt-3">
          <span className="font-mono text-xs font-bold text-green-400 bg-green-900/50 px-2 py-1 rounded">POST</span>
          <span className="font-mono text-sm text-slate-300">{API_URL}/agent/v1/mcp/messages/</span>
        </div>
      </section>
      
      <section id="mcp-methods">
          <h2 className="text-3xl font-bold text-slate-100 mb-4 flex items-center"><BrainCircuit className="w-7 h-7 mr-3 text-purple-400"/>MCP Methods</h2>
          <p className="text-slate-400 mb-4">
            The agent endpoint supports all standard MCP methods, including tool calls. You can interact with the memory system using methods like <code className="font-mono text-sm">tools/list</code>, <code className="font-mono text-sm">resources/list</code>, and <code className="font-mono text-sm">tools/call</code>.
          </p>
          <div className="p-4 border border-sky-700/80 bg-sky-900/50 rounded-lg text-sky-300 text-sm">
              The architecture has been unified. The agent endpoint is a fully-featured MCP server, providing the same capabilities as the internal system used by Claude.
          </div>
      </section>

      <section id="available-tools">
        <h2 className="text-3xl font-bold text-slate-100 mb-4 flex items-center"><ListTree className="w-7 h-7 mr-3 text-purple-400"/>Available Tools</h2>
        <p className="text-slate-400 mb-6">
          The Agent API exposes several powerful tools to interact with the user's memory. You call these tools using the <code className="font-mono text-sm">tools/call</code> MCP method.
        </p>
        <div className="space-y-8">
          {/* add_memories tool */}
          <div className="p-6 border border-slate-700/50 rounded-lg bg-slate-900/40">
            <h3 className="font-mono text-lg text-pink-400 mb-2">add_memories</h3>
            <p className="text-slate-400 mb-4">
              Adds one or more new memories to the user's memory store. Each memory should be a distinct piece of information.
            </p>
            <h4 className="font-semibold text-slate-200 mb-2">Input Schema:</h4>
            <CodeBlock lang="json" code={`
{
  "text": {
    "type": "string",
    "description": "The memory text to add. For multiple, use a newline-separated string."
  }
}
            `} />
            <h4 className="font-semibold text-slate-200 mt-4 mb-2">Example Payload:</h4>
            <CodeBlock lang="json" code={`
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
      "name": "add_memories",
      "arguments": {
          "text": "The user is interested in learning about generative adversarial networks (GANs)."
      }
  },
  "id": 1
}
            `} />
          </div>

          {/* search_memories tool */}
          <div className="p-6 border border-slate-700/50 rounded-lg bg-slate-900/40">
            <h3 className="font-mono text-lg text-pink-400 mb-2">search_memories</h3>
            <p className="text-slate-400 mb-4">
              Performs a semantic search over the user's memories and returns the most relevant results.
            </p>
            <h4 className="font-semibold text-slate-200 mb-2">Input Schema:</h4>
            <CodeBlock lang="json" code={`
{
  "query": {
    "type": "string",
    "description": "The query to search for."
  }
}
            `} />
            <h4 className="font-semibold text-slate-200 mt-4 mb-2">Example Payload:</h4>
            <CodeBlock lang="json" code={`
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
      "name": "search_memories",
      "arguments": {
          "query": "What are my project preferences?"
      }
  },
  "id": 2
}
            `} />
          </div>
        </div>
      </section>

      <section id="python-example">
        <h2 className="text-3xl font-bold text-slate-100 mb-4 flex items-center"><Puzzle className="w-7 h-7 mr-3 text-purple-400"/>Python Example</h2>
        <p className="text-slate-400 mb-4">
          Here is a simple example of how to use the API with Python's <code className="font-mono text-sm">requests</code> library to add a new memory.
        </p>
        <CodeBlock lang="python" code={`
import requests
import json
import os

# It's best practice to load your key from an environment variable
API_KEY = os.environ.get("JEAN_API_KEY")
API_URL = "${API_URL}/agent/v1/mcp/messages/"

if not API_KEY:
    raise ValueError("JEAN_API_KEY environment variable not set!")

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

payload = {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "add_memories",
        "arguments": {
            "text": "The user is interested in learning about generative adversarial networks (GANs)."
        }
    },
    "id": 1
}

try:
    response = requests.post(API_URL, headers=headers, data=json.dumps(payload))
    response.raise_for_status()  # Raises an exception for bad status codes
    
    print("Response:", response.json())

except requests.exceptions.RequestException as e:
    print(f"An error occurred: {e}")
        `} />
        <p className="text-slate-400 mt-4">
          A successful call to <code className="font-mono text-sm">add_memories</code> will return a confirmation message.
        </p>
        <CodeBlock lang="json" code={`
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": "Successfully added 1 new memory."
  }
}
`} />
      </section>

      <section id="curl-example">
        <h2 className="text-3xl font-bold text-slate-100 mb-4 flex items-center"><Terminal className="w-7 h-7 mr-3 text-purple-400"/>cURL Example</h2>
        <p className="text-slate-400 mb-4">
          You can also interact with the API directly from your terminal using cURL. This example lists the available tools.
        </p>
        <CodeBlock lang="bash" code={`
curl -X POST ${API_URL}/agent/v1/mcp/messages/ \\
  -H "Authorization: Bearer YOUR_JEAN_API_KEY" \\
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
      
      <section id="architecture-diagram">
          <h2 className="text-3xl font-bold text-slate-100 mb-4 flex items-center"><Server className="w-7 h-7 mr-3 text-purple-400"/>Architecture</h2>
          <p className="text-slate-400 mb-4">
            The final architecture ensures that production UI and Claude integrations are completely isolated from the new Agent API path, which now has its own dedicated, fully-featured MCP handler.
            <span className="block text-sm text-slate-500 mt-1">Click the diagram to expand.</span>
          </p>
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