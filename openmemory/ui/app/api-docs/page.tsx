"use client";

import React, { useState, useEffect, useRef } from 'react';
import { GitBranch, Shield, BookOpen, Puzzle, Terminal, Code, Server, Key, BrainCircuit, Copy, Check, LucideIcon, ListTree, Bot, Lightbulb, Briefcase, Share2, Component, PlayCircle, Cpu, FileText, Sparkles, AlertTriangle } from 'lucide-react';
import { usePathname, useRouter } from 'next/navigation';
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import ParticleNetwork from '@/components/landing/ParticleNetwork';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';

const InteractiveDemo = () => {
  const [isRunning, setIsRunning] = useState(false);
  const [step, setStep] = useState(0);

  const steps = [
    {
      title: "1. Store Memory with Tags",
      icon: FileText,
      lang: "json",
      code: `{
  "method": "tools/call",
  "params": {
    "name": "add_memories",
    "arguments": {
      "text": "The new frontend component should be built with React and TypeScript.",
      "tags": ["work", "project-alpha", "frontend"]
    }
  }
}`
    },
    {
      title: "2. Search with Tag Filtering",
      icon: Cpu,
      lang: "json",
      code: `{
  "method": "tools/call",
  "params": {
    "name": "search_memory_v2",
    "arguments": {
      "query": "tech stack",
      "tags_filter": ["project-alpha", "frontend"]
    }
  }
}`
    },
    {
      title: "3. Receive Filtered Results",
      icon: Sparkles,
      lang: "json",
      code: `{
  "result": {
    "results": [
      {
        "id": "...",
        "text": "The new frontend component should be built with React and TypeScript.",
        "metadata": { "tags": ["work", "project-alpha", "frontend"] }
      }
    ]
  }
}`
    }
  ];

  const handleRun = () => {
    if (isRunning) return;
    setIsRunning(true);
    setStep(1);

    setTimeout(() => setStep(2), 1500);
    setTimeout(() => setStep(3), 3000);
    setTimeout(() => {
      setIsRunning(false);
    }, 3500);
  };

  const handleReset = () => {
    setStep(0);
    setIsRunning(false);
  }

  return (
    <div className="p-6 border border-border rounded-lg bg-card/50 backdrop-blur-sm relative overflow-hidden">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold text-foreground">Live API Walkthrough</h3>
        {step === 3 ? (
           <Button variant="ghost" size="sm" onClick={handleReset}>Reset</Button>
        ) : (
           <Button variant="default" size="sm" onClick={handleRun} disabled={isRunning}>
            <PlayCircle className="w-4 h-4 mr-2"/>
            Run Demo
          </Button>
        )}
      </div>
      <p className="text-sm text-muted-foreground mb-6">
        See how to use metadata tags to store and retrieve context-specific memories.
      </p>

      <div className="space-y-4">
        <AnimatePresence>
          {steps.slice(0, step).map((item, index) => {
            const Icon = item.icon;
            return (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.5 }}
              >
                <h4 className="font-semibold text-foreground/90 text-sm mb-2 flex items-center">
                  <Icon className="w-4 h-4 mr-2 text-muted-foreground"/>
                  {item.title}
                </h4>
                <CodeBlock code={item.code} lang={item.lang} />
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>

      {isRunning && step < 3 && (
        <div className="mt-4 flex items-center text-sm text-muted-foreground">
          <Cpu className="w-4 h-4 mr-2 animate-pulse"/>
          Simulating API call...
        </div>
      )}
    </div>
  );
};

// A simple syntax-highlighted code block component with a copy button
const CodeBlock = ({ code, lang = 'bash' }: { code: string, lang?: string }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code.trim());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000); // Reset after 2 seconds
  };
  
  const lines = code.trim().split('\n');

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
              styledLine = styledLine.replace(/(X-Api-Key:)/g, '<span class="text-sky-400">$&</span>');
          } else if (lang === 'python') {
              styledLine = styledLine.replace(/(#.*$)/g, '<span class="text-slate-500">$&</span>');
              styledLine = styledLine.replace(/(".*?"|'.*?')/g, '<span class="text-emerald-400">$&</span>');
              styledLine = styledLine.replace(/\b(from|import|def|return|print|if|for|in|not|try|except|raise|as)\b/g, '<span class="text-pink-400">$&</span>');
              styledLine = styledLine.replace(/\b(requests|json|os)\b/g, '<span class="text-sky-400">$&</span>');
          } else if (lang === 'mermaid') {
              return <div key={i}><pre className="text-slate-200 whitespace-pre-wrap">{line}</pre></div>;
          } else if (lang === 'json') {
             // Basic JSON highlighting for keys
             styledLine = styledLine.replace(/"([^"]+)":/g, '<span class="text-sky-300">"$1"</span>:');
             // Highlight string values
             styledLine = styledLine.replace(/: "([^"]*)"/g, ': <span class="text-emerald-400">"$1"</span>');
             // Highlight numbers
             styledLine = styledLine.replace(/: ([\d.]+)/g, ': <span class="text-purple-400">$1</span>');
             // Highlight booleans
             styledLine = styledLine.replace(/: (true|false)/g, ': <span class="text-pink-400">$1</span>');
             // Highlight null
             styledLine = styledLine.replace(/: (null)/g, ': <span class="text-slate-500">$1</span>');
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
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  useEffect(() => {
    if (!isClient || !ref.current) return;
    
    const refCurrent = ref.current; // Create a stable variable
    refCurrent.innerHTML = ''; // Clear previous diagram

    const render = async () => {
      try {
        const mermaid = (await import('mermaid')).default;
        const id = `mermaid-graph-${Math.random().toString(36).substring(2, 9)}`;
        
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
        
        const { svg } = await mermaid.render(id, chart);
        refCurrent.innerHTML = svg;
      } catch (error) {
        console.error("Mermaid rendering failed:", error);
        refCurrent.innerHTML = `<p class="text-red-400">Error rendering diagram.</p>`;
      }
    };
    render();
  }, [chart, isClient]);

  if (!isClient) {
    return (
      <div className="flex justify-center items-center p-4 bg-slate-900/70 rounded-lg border border-slate-700/50 min-h-[300px]">
        <div className="text-slate-400">Loading diagram...</div>
      </div>
    );
  }
  
  return (
    <div className="flex justify-center items-center p-4 bg-slate-900/70 rounded-lg border border-slate-700/50 min-h-[300px]">
      <div ref={ref} className="w-full h-full" />
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
    <div className="min-h-screen bg-background text-foreground">
      <div className="absolute inset-0 z-0 h-full w-full">
        <ParticleNetwork id="api-docs-particles" className="h-full w-full" interactive={false} particleCount={80} />
      </div>
      <div className="relative z-10 container mx-auto px-4 sm:px-6 lg:px-8">
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
                       ? 'bg-muted text-foreground'
                       : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
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
  { href: '#metadata-tags', label: 'Metadata & Tags', icon: Component },
  { href: '#available-tools', label: 'Available Tools', icon: ListTree },
  { href: '#key-concepts', label: 'Key Concepts', icon: BrainCircuit },
  { href: '#error-handling', label: 'Error Handling', icon: AlertTriangle },
  { href: '#example-use-cases', label: 'Example Use Cases', icon: Lightbulb },
  { href: '#python-example', label: 'Python Examples', icon: Code },
  { href: '#curl-example', label: 'cURL Examples', icon: Terminal },
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
    subgraph "Clients"
        A["Claude Desktop"] --> H;
        E["API User<br/>(Programmatic Access)"] --> H;
    end

    subgraph "Unified Jean Memory API"
        H["POST /mcp/messages/"] -- "All requests" --> I{Dual-Path Authentication};
        I -- "x-user-id + x-client-name" --> J["Claude Tools Schema<br/>(Simple, no tags)"];
        I -- "X-Api-Key" --> K["API Tools Schema<br/>(Advanced, with tags)"];
        
        J --> L{Tool Executor};
        K --> L;
        
        L -- "Executes requested tool<br/>e.g., add_memories, search_memory_v2" --> M[mem0 Library];
    end

    subgraph "Backend Infrastructure"
        M -- "Stores & retrieves data" --> N((Qdrant<br/>Vector Database));
    end
    
    classDef client fill:#1d4ed8,stroke:#60a5fa,color:#fafafa,stroke-width:1px;
    classDef api fill:#166534,stroke:#4ade80,color:#fafafa,stroke-width:1px;
    classDef backend fill:#7c2d12,stroke:#fb923c,color:#fafafa,stroke-width:1px;

    class A,E client;
    class H,I,J,K,L,M api;
    class N backend;
  `;

  return (
    <DocsLayout navItems={navItems}>
      <section id="introduction">
        <h1 className="text-4xl font-bold text-foreground mb-4">Jean Memory API</h1>
        <p className="text-xl text-muted-foreground mb-6">
          Build personal or enterprise agents with human-like memory
        </p>
        
        <div className="my-8">
          <InteractiveDemo />
        </div>

        <p className="text-lg text-muted-foreground mb-4">
          Welcome to the Jean Memory API documentation. This API provides a robust, unified memory layer for your AI applications, featuring secure API key authentication and powerful metadata filtering for advanced use cases.
        </p>
        <div className="flex items-center gap-4 p-4 bg-green-950/50 border border-green-800/60 rounded-lg">
          <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
          <p className="text-green-300 text-sm">
            <strong>Production Ready:</strong> Zero breaking changes, dual-path authentication, and enterprise-grade security.
          </p>
        </div>
      </section>

      <section id="authentication">
        <h2 className="text-3xl font-bold text-foreground mb-4">Authentication</h2>
        <p className="text-muted-foreground mb-4">
          The API supports a dual-path authentication system to ensure both maximum flexibility for new developers and 100% backward compatibility for existing integrations like Claude Desktop.
        </p>
        <div className="space-y-6">
          <div className="p-4 border border-border bg-card rounded-lg">
            <h3 className="font-semibold text-foreground text-lg flex items-center mb-3"><Key className="w-5 h-5 mr-2 text-muted-foreground"/>Option 1: API Key (Recommended for API Users)</h3>
            <p className="text-muted-foreground text-sm mt-1 mb-2">
              For programmatic access, include your API key in the <code className="font-mono text-xs bg-muted px-1 rounded">X-Api-Key</code> header. This unlocks advanced features like metadata tagging and filtering.
            </p>
            <CodeBlock lang="http" code={`X-Api-Key: jean_sk_s8ad0fI7x2VD2KnyLewH0e3ajuRV_1mdWGgnsBJ6VA8`} />
          </div>
          <div className="p-4 border border-border bg-card rounded-lg">
            <h3 className="font-semibold text-foreground text-lg flex items-center mb-3"><Component className="w-5 h-5 mr-2 text-muted-foreground"/>Option 2: Headers (Claude Desktop & UI)</h3>
            <p className="text-muted-foreground text-sm">
              Used internally by existing integrations. Requires both <code className="font-mono text-xs bg-muted px-1 rounded">x-user-id</code> and <code className="font-mono text-xs bg-muted px-1 rounded">x-client-name</code> headers. This path serves a simplified toolset to ensure stability.
            </p>
            <CodeBlock lang="http" code={`x-user-id: your-supabase-user-id
x-client-name: your-app-name`} />
          </div>
        </div>
      </section>
      
      <section id="endpoints">
        <h2 className="text-3xl font-bold text-foreground mb-4">Unified API Endpoint</h2>
        <p className="text-muted-foreground mb-4">
          All interactions for both authentication methods use a single, unified MCP endpoint. This endpoint accepts POST requests with a JSON-RPC 2.0 payload to execute memory tools.
        </p>
        <div className="flex items-center gap-2 mt-3">
          <span className="font-mono text-xs font-bold text-foreground bg-muted px-2 py-1 rounded">POST</span>
          <span className="font-mono text-sm text-muted-foreground">{API_URL}/mcp/messages/</span>
        </div>
         <div className="mt-6">
            <h3 className="text-xl font-semibold text-foreground mb-2">Architecture Diagram</h3>
            <p className="text-muted-foreground mb-4">This diagram illustrates how requests from different clients are routed through the unified endpoint to their respective tool schemas. <span className="block text-sm text-muted-foreground mt-1">Click the diagram to expand.</span></p>
             <div className="cursor-zoom-in" onClick={() => setIsDiagramModalOpen(true)}>
                <MermaidDiagram chart={architectureDiagram} />
            </div>
         </div>
      </section>

      <section id="metadata-tags">
        <h2 className="text-3xl font-bold text-foreground mb-4">Metadata & Tags</h2>
        <p className="text-muted-foreground mb-4">
          The API supports powerful metadata tagging for memory segmentation and organization. This feature allows API users to categorize memories and perform sophisticated filtering for multi-tenant applications, project isolation, and context-aware search.
        </p>
        
        <Alert variant="default" className="bg-amber-950/50 border-amber-800/60 text-amber-300 mb-6">
          <Component className="h-4 w-4 text-amber-400" />
          <AlertTitle>API Users Only Feature</AlertTitle>
          <AlertDescription>
            Metadata and tag filtering capabilities are exclusively available to users authenticating with an <code className="font-mono text-xs">X-Api-Key</code>. Claude Desktop integrations receive a simplified toolset to ensure maximum stability and prevent UI complexity.
          </AlertDescription>
        </Alert>

        <div className="space-y-8">
          <div className="p-4 border border-border bg-card rounded-lg">
            <h3 className="font-semibold text-foreground text-lg flex items-center mb-3">
              <BrainCircuit className="w-5 h-5 mr-2 text-muted-foreground"/>
              Adding Tagged Memories
            </h3>
            <p className="text-muted-foreground text-sm mb-3">
              Use the optional <code className="font-mono text-xs bg-muted px-1 rounded">tags</code> parameter in the <code className="font-mono text-xs bg-muted px-1 rounded">add_memories</code> tool to categorize your information. Tags should be an array of strings.
            </p>
            <CodeBlock lang="json" code={`{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "add_memories",
    "arguments": {
      "text": "Project Alpha uses React with TypeScript and requires daily standups at 9 AM",
      "tags": ["work", "project-alpha", "meetings", "react"]
    }
  },
  "id": "req-123"
}`} />
          </div>

          <div className="p-4 border border-border bg-card rounded-lg">
            <h3 className="font-semibold text-foreground text-lg flex items-center mb-3">
              <Server className="w-5 h-5 mr-2 text-muted-foreground"/>
              Filtering by Tags
            </h3>
            <p className="text-muted-foreground text-sm mb-3">
              Use the <code className="font-mono text-xs bg-muted px-1 rounded">search_memory_v2</code> tool with the <code className="font-mono text-xs bg-muted px-1 rounded">tags_filter</code> parameter to find memories that contain specific tags.
            </p>
            <CodeBlock lang="json" code={`{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "search_memory_v2",
    "arguments": {
      "query": "meeting schedule",
      "tags_filter": ["work", "project-alpha"]
    }
  },
  "id": "req-124"
}`} />
            <div className="mt-4 p-3 bg-muted/50 border border-border rounded text-sm">
              <strong className="text-foreground">⚡ Filtering Logic: AND</strong>
              <p className="text-muted-foreground mt-1">
                The filtering logic uses an <strong>AND</strong> condition. The search will only return memories that contain <strong>ALL</strong> of the tags specified in the <code className="font-mono text-xs">tags_filter</code> array.
              </p>
            </div>
          </div>
          
           <div className="p-4 border border-border bg-card rounded-lg">
            <h3 className="font-semibold text-foreground text-lg flex items-center mb-3">
              <Lightbulb className="w-5 h-5 mr-2 text-muted-foreground"/>
              Best Practices for Tagging
            </h3>
            <div className="mt-3 p-3 bg-muted/50 border border-border rounded text-sm">
              <ul className="list-disc list-inside space-y-2 text-muted-foreground">
                <li><strong>Consistency is Key:</strong> Use a consistent naming convention (e.g., lowercase, kebab-case: `project-alpha`).</li>
                <li><strong>Create Namespaces:</strong> Use prefixes to create logical groups (e.g., `proj:alpha`, `client:acme`, `source:slack`).</li>
                <li><strong>Be Descriptive:</strong> Keep tags short but clear. Limit to 3-5 tags per memory for optimal performance and clarity.</li>
                <li><strong>Plan for Queries:</strong> Design your tags based on how you plan to filter and retrieve the data later.</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section id="available-tools">
        <h2 className="text-3xl font-bold text-foreground mb-4">Available Tools</h2>
        <p className="text-muted-foreground mb-6">
          The API exposes powerful, high-performance tools for memory interaction. The exact tools and parameters available depend on your authentication method.
        </p>
        <Alert variant="default" className="mb-8 bg-blue-950/50 border-blue-800/60 text-blue-300">
            <Share2 className="h-4 w-4 text-blue-400" />
            <AlertTitle>Client-Specific Tool Schemas</AlertTitle>
            <AlertDescription>
                To ensure stability and backward compatibility, the API serves different tool schemas based on the client:
                <ul className="list-disc list-inside mt-2">
                  <li><strong>API Users (<code className="font-mono text-xs">X-Api-Key</code>):</strong> Receive the full, advanced toolset including <code className="font-mono text-xs">search_memory_v2</code> and optional <code className="font-mono text-xs">tags</code> parameters.</li>
                  <li><strong>Claude Desktop & UI Users:</strong> Receive a simpler, reliable set of tools without metadata parameters to prevent issues in legacy clients.</li>
                </ul>
            </AlertDescription>
        </Alert>
        <div className="space-y-8">

          {/* add_memories tool */}
          <div className="p-6 border border-border rounded-lg bg-card">
            <h3 className="font-mono text-lg text-primary mb-2">add_memories</h3>
            <p className="text-muted-foreground mb-4">
              Stores information in long-term memory. Use this to remember key facts, user preferences, or details from conversations.
            </p>
            <Alert variant="destructive" className="mb-4">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Important: Non-Deterministic Behavior</AlertTitle>
              <AlertDescription>
                This tool does **not** store text verbatim. It uses an internal LLM to extract core facts, which may lead to rephrasing. Do not rely on exact string matching to verify stored memories. Instead, check for the presence of unique keywords or identifiers.
              </AlertDescription>
            </Alert>
            <h4 className="font-semibold text-foreground mb-2">Input Schema:</h4>
            <CodeBlock lang="json" code={`{
  "text": {
    "type": "string",
    "description": "Important information to remember about the user (facts, preferences, insights, etc.)"
  },
  "tags": {
    "type": "array",
    "items": { "type": "string" },
    "description": "[API Users Only] Optional list of strings to categorize the memory (e.g., ['work', 'project-alpha'])."
  }
}`} />
          </div>

          {/* search_memory tool */}
          <div className="p-6 border border-border rounded-lg bg-card">
            <h3 className="font-mono text-lg text-primary mb-2">search_memory</h3>
            <p className="text-muted-foreground mb-4">
              Performs a semantic search over memories. This is the standard search tool available to all clients and does not support tag filtering.
            </p>
            <h4 className="font-semibold text-foreground mb-2">Input Schema:</h4>
            <CodeBlock lang="json" code={`{
  "query": {
    "type": "string",
    "description": "Keywords or phrases to search for"
  },
  "limit": {
    "type": "integer",
    "description": "Maximum number of results to return (default: 10)"
  }
}`} />
          </div>

          {/* search_memory_v2 tool */}
          <div className="p-6 border border-border rounded-lg bg-card">
            <h3 className="font-mono text-lg text-primary mb-2">search_memory_v2 <span className="text-xs font-sans text-white bg-zinc-700 px-2 py-1 rounded-full ml-2">API Users</span></h3>
            <p className="text-muted-foreground mb-4">
              An enhanced search tool that allows for powerful filtering by tags. This is the recommended search tool for all new development using API keys.
            </p>
            <h4 className="font-semibold text-foreground mb-2">Input Schema:</h4>
            <CodeBlock lang="json" code={`{
  "query": {
    "type": "string",
    "description": "Keywords or phrases to search for"
  },
  "limit": {
    "type": "integer",
    "description": "Maximum number of results to return (default: 10)"
  },
  "tags_filter": {
    "type": "array",
    "items": { "type": "string" },
    "description": "Optional. A list of tags to filter results. Returns only memories containing ALL specified tags."
  }
}`} />
            <h4 className="font-semibold text-foreground mt-4 mb-2">Example Payload:</h4>
            <CodeBlock lang="json" code={`{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "search_memory_v2",
    "arguments": {
      "query": "database performance",
      "tags_filter": ["work", "project-gamma", "backend"]
    }
  },
  "id": "req-125"
}`} />
          </div>
          
          {/* Other tools */}
          <div className="p-6 border border-border rounded-lg bg-card">
            <h3 className="font-mono text-lg text-primary mb-2">list_memories</h3>
             <p className="text-muted-foreground mb-4">Browse recently stored memories. Useful for getting a quick overview or for confirming a memory was received before it is fully indexed for search.</p>
          </div>
          <div className="p-6 border border-border rounded-lg bg-card">
            <h3 className="font-mono text-lg text-primary mb-2">ask_memory</h3>
            <p className="text-muted-foreground mb-4">Provides a fast, conversational answer to a natural language question. Optimized for speed and should be preferred for simple queries.</p>
          </div>
           <div className="p-6 border border-border rounded-lg bg-card">
            <h3 className="font-mono text-lg text-primary mb-2">deep_memory_query</h3>
             <p className="text-muted-foreground mb-4">
               A comprehensive, slow search that analyzes full documents. Use this for deep analysis that requires synthesizing information from large bodies of text. This is by far my favorite and most powerful tool.
             </p>
             <h4 className="font-semibold text-foreground mb-2">Input Schema:</h4>
             <CodeBlock lang="json" code={`{
  "search_query": {
    "type": "string",
    "description": "The complex, natural language question for deep analysis."
  }
}`} />
            <h4 className="font-semibold text-foreground mt-4 mb-2">Example Payload:</h4>
            <CodeBlock lang="json" code={`{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "deep_memory_query",
    "arguments": {
      "search_query": "What is the philosophical throughline of my recent essays?"
    }
  },
  "id": "req-126"
}`} />
          </div>
        </div>
      </section>

      <section id="key-concepts">
        <h2 className="text-3xl font-bold text-foreground mb-4">Key Concepts for Developers</h2>
        <p className="text-muted-foreground mb-4">
          Understanding these architectural concepts is crucial for building reliable and performant applications with the Jean Memory API.
        </p>
        <Alert variant="default" className="bg-blue-950/50 border-blue-800/60 text-blue-300 mb-6">
          <BrainCircuit className="h-4 w-4 text-blue-400" />
          <AlertTitle>Core Concept: Asynchronous Indexing</AlertTitle>
          <AlertDescription>
            When you add a memory using <code className="font-mono text-xs">add_memories</code>, it is ingested immediately but is **not instantly searchable**. The memory enters a queue to be processed, embedded, and indexed into the vector database. This process is highly optimized but can take a few seconds.
             <ul className="list-disc list-inside space-y-2 text-blue-200/80 text-sm mt-3">
                <li>
                  <strong>Best Practice:</strong> Decouple write and read operations. Do not design workflows that add a memory and then immediately search for it. Assume an indexing delay.
                </li>
                <li>
                  <strong>Confirmation:</strong> Use <code className="font-mono text-xs">list_memories</code> to confirm a memory was *received*, as it often shows entries before they are fully indexed for search.
                </li>
              </ul>
          </AlertDescription>
        </Alert>
      </section>

      <section id="error-handling">
        <h2 className="text-3xl font-bold text-foreground mb-4">Error Handling</h2>
        <p className="text-muted-foreground mb-4">
          The API uses standard HTTP status codes and provides detailed JSON-RPC error objects. We perform robust parameter validation on all tool calls.
        </p>
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Example: Invalid Parameters (HTTP 422)</AlertTitle>
          <AlertDescription>
            If you provide incorrect parameters (e.g., missing a required argument or using the wrong type), the API returns an <code className="font-mono text-xs">HTTP 422 Unprocessable Entity</code> status with a <code className="font-mono text-xs">-32602</code> error code in the body to help you debug.
          </AlertDescription>
        </Alert>
         <h4 className="font-semibold text-foreground mt-6 mb-2">Example Error Response:</h4>
         <CodeBlock lang="json" code={`
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32602,
    "message": "Invalid parameters for tool 'add_memories': 1 validation error for ToolInput\\narguments\\n  text\\n    Field required [type=missing, ...]"
  },
  "id": "req-123"
}
`} />
      </section>

      <section id="example-use-cases">
        <h2 className="text-3xl font-bold text-foreground mb-4">Example Use Cases for Tagging</h2>
        <p className="text-muted-foreground mb-6">
          Metadata tagging unlocks powerful workflows for sophisticated AI applications. Here are a few examples.
        </p>
        <div className="space-y-8">

          <div className="p-6 border border-border rounded-lg bg-card">
            <h3 className="text-lg font-semibold text-foreground mb-2">🏢 Multi-Tenant Applications</h3>
            <p className="text-muted-foreground mb-4">
              Isolate data between different customers or users within your application. By tagging each memory with a unique `client_id`, you can ensure that searches for one client never return data from another.
            </p>
            <div className="bg-muted/50 p-3 rounded text-sm">
              <strong className="text-foreground">Example Flow:</strong>
              <ol className="list-decimal list-inside mt-2 space-y-1 text-muted-foreground">
                <li>Agent adds memory for Client A: `add_memories(text: "...", tags: ["client:acme", "user:123"])`</li>
                <li>Agent adds memory for Client B: `add_memories(text: "...", tags: ["client:globex", "user:456"])`</li>
                <li>When serving Client A, agent searches: `search_memory_v2(query: "...", tags_filter: ["client:acme"])`</li>
              </ol>
            </div>
          </div>

          <div className="p-6 border border-border rounded-lg bg-card">
            <h3 className="text-lg font-semibold text-foreground mb-2">📋 Project Management Agent</h3>
            <p className="text-muted-foreground mb-4">
              Build an agent that helps teams stay organized. Tag memories with project names, sprint numbers, and task types to create a searchable knowledge base for each project.
            </p>
             <div className="bg-muted/50 p-3 rounded text-sm">
              <strong className="text-foreground">Example Flow:</strong>
              <ol className="list-decimal list-inside mt-2 space-y-1 text-muted-foreground">
                <li>Agent ingests a meeting summary: `add_memories(text: "...", tags: ["proj:phoenix", "sprint:3", "meeting-notes"])`</li>
                <li>A developer asks: "What were the action items from the last Project Phoenix sprint 3 meeting?"</li>
                <li>Agent searches: `search_memory_v2(query: "action items", tags_filter: ["proj:phoenix", "sprint:3"])`</li>
              </ol>
            </div>
          </div>
        </div>
      </section>

      <section id="python-example">
        <h2 className="text-3xl font-bold text-foreground mb-4">Python Examples</h2>
        <p className="text-muted-foreground mb-4">
          Here's how to interact with the API using Python. Ensure your API key is set as an environment variable (`JEAN_API_KEY`).
        </p>
        
        <div className="p-6 border border-border rounded-lg bg-card mb-8">
            <h3 className="text-lg font-semibold text-foreground mb-2">Basic Example: Add and Search</h3>
            <p className="text-muted-foreground mb-4">
              A simple demonstration of adding a tagged memory and then retrieving it with a filtered search.
            </p>
            <CodeBlock lang="python" code={`
import requests
import json
import os
import time

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

# 1. Add a memory with tags
print("Adding a memory for 'project-zeta'...")
add_payload = {
    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
    "params": {
        "name": "add_memories",
        "arguments": {
            "text": "The database for project-zeta needs to be migrated to Postgres 15.",
            "tags": ["work", "project-zeta", "database", "backend"]
        }
    }
}
add_result = call_jean_api(add_payload)
print("Add result:", add_result)

# Wait for indexing
print("\\nWaiting 5 seconds for indexing...")
time.sleep(5)

# 2. Search for the memory using a tag filter
print("Searching for memories tagged with 'project-zeta' and 'database'...")
search_payload = {
    "jsonrpc": "2.0", "id": 2, "method": "tools/call",
    "params": {
        "name": "search_memory_v2",
        "arguments": {
            "query": "database migration",
            "tags_filter": ["project-zeta", "database"]
        }
    }
}
search_results = call_jean_api(search_payload)
print("\\nSearch results:")
print(json.dumps(search_results, indent=2))
        `} />
        </div>
        
        <div className="p-6 border border-border rounded-lg bg-card">
            <h3 className="text-lg font-semibold text-foreground mb-2">Advanced Example: Cross-Source Context Agent</h3>
            <p className="text-muted-foreground mb-4">
              A more complex workflow where an agent uses shared, tagged memory to provide context on an issue by combining information from different sources (e.g., Slack and Jira).
            </p>
            <CodeBlock lang="python" code={`
# (Assumes helper function 'call_jean_api' from previous example)

# --- Step 1: An agent ingests memories from different sources ---
print("--- Step 1: Ingesting memories from Slack and Jira ---")
call_jean_api({
    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
    "params": { "name": "add_memories", "arguments": {
        "text": "User 'dave' in #bugs: 'Can't reset my password, the link is broken.'",
        "tags": ["source:slack", "bug-report", "auth-flow"]
    }}
})
call_jean_api({
    "jsonrpc": "2.0", "id": 2, "method": "tools/call",
    "params": { "name": "add_memories", "arguments": {
        "text": "Jira Ticket JIRA-123 created for 'Password reset link broken'. Assigned to eng-team.",
        "tags": ["source:jira", "ticket:JIRA-123", "auth-flow", "status:open"]
    }}
})
print("Memories added.")
time.sleep(5) # Wait for indexing

# --- Step 2: A developer's agent seeks context on the Jira ticket ---
print("\\n--- Step 2: Agent searching for all context related to 'auth-flow' ---")
search_payload = {
    "jsonrpc": "2.0", "id": 3, "method": "tools/call",
    "params": {
        "name": "search_memory_v2",
        "arguments": {
            "query": "password reset",
            "tags_filter": ["auth-flow"] # Find all related memories
        }
    }
}
search_results = call_jean_api(search_payload)

# --- Step 3: The agent synthesizes the results for the developer ---
print("\\n--- Step 3: Agent synthesizing response ---")
if search_results and search_results.get('result', {}).get('results'):
    context = ""
    for res in search_results['result']['results']:
        source = "N/A"
        if res.get('metadata', {}).get('tags'):
            for tag in res['metadata']['tags']:
                if tag.startswith('source:'):
                    source = tag.split(':')[1]
        context += f"- [{source.upper()}] {res['text']}\\n"
    
    final_answer = f"""
Here is the full context for the password reset issue:

{context}
This combines the original user report from Slack with the formal Jira ticket details.
"""
    print(final_answer)
else:
    print("Could not find any context for that ticket.")
        `} />
        </div>
      </section>

      <section id="curl-example">
        <h2 className="text-3xl font-bold text-foreground mb-4">cURL Examples</h2>
        <p className="text-muted-foreground mb-4">
          You can also interact with the API directly from your terminal using cURL.
        </p>

        <div className="p-6 border border-border rounded-lg bg-card mb-8">
            <h3 className="text-lg font-semibold text-foreground mb-2">Add a Memory with Tags</h3>
            <CodeBlock lang="bash" code={`
curl -X POST ${API_URL}/mcp/messages/ \\
  -H "X-Api-Key: YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "add_memories",
      "arguments": {
        "text": "The Q3 financial report is due on October 15th.",
        "tags": ["work", "finance", "deadline", "q3-report"]
      }
    },
    "id": "curl-add-1"
  }'
        `} />
        </div>

        <div className="p-6 border border-border rounded-lg bg-card">
            <h3 className="text-lg font-semibold text-foreground mb-2">Search with a Tag Filter</h3>
            <CodeBlock lang="bash" code={`
curl -X POST ${API_URL}/mcp/messages/ \\
  -H "X-Api-Key: YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "search_memory_v2",
      "arguments": {
        "query": "financial report",
        "tags_filter": ["finance", "deadline"]
      }
    },
    "id": "curl-search-1"
  }'
        `} />
        </div>
      </section>
      
      {isDiagramModalOpen && (
        <DiagramModal chart={architectureDiagram} onClose={() => setIsDiagramModalOpen(false)} />
      )}

    </DocsLayout>
  );
};

export default ApiDocsPage;