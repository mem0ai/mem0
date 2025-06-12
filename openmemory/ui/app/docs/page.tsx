"use client";

import React, { useState, useEffect } from 'react';
import { GitBranch, Shield, BookOpen, Puzzle, Terminal, DownloadCloud, Copy, Check, Code } from 'lucide-react';
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
          let styledLine = line;
          if (lang === 'bash') {
              styledLine = line.replace(/curl/g, '<span class="text-pink-400">curl</span>');
              styledLine = styledLine.replace(/(-X POST|-H|-d)/g, '<span class="text-cyan-400">$&</span>');
              styledLine = styledLine.replace(/(https:\/\/[^\s]+)/g, '<span class="text-amber-400">$&</span>');
          } else if (lang === 'python') {
              styledLine = styledLine.replace(/(#.*$)/g, '<span class="text-slate-500">$&</span>');
              styledLine = styledLine.replace(/(".*?")/g, '<span class="text-emerald-400">$&</span>');
              styledLine = styledLine.replace(/\b(from|import|def|return|print|if|for|in|not)\b/g, '<span class="text-pink-400">$&</span>');
              styledLine = styledLine.replace(/\b(JeanMemoryClient|add_tagged_memory|search_by_tags|OpenAI)\b/g, '<span class="text-yellow-400">$&</span>');
              styledLine = styledLine.replace(/\b(True|False|None)\b/g, '<span class="text-sky-400">$&</span>');
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

// Navigation items
const navItems = [
  { href: '#introduction', label: 'Introduction', icon: BookOpen },
  { href: '#authentication', label: 'Authentication', icon: Shield },
  { href: '#endpoints', label: 'API Endpoints', icon: GitBranch },
  { href: '#sdk', label: 'Python SDK', icon: Puzzle },
  { href: '#example', label: 'Example', icon: Code },
];

const DocsPage = () => {
  const API_URL = "https://api.jeanmemory.com";
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
  }, []);

  const handleNavClick = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    e.preventDefault();
    setActiveId(href.substring(1));
    document.getElementById(href.substring(1))?.scrollIntoView({
      behavior: 'smooth',
      block: 'start'
    });
    // Update URL without page reload
    router.push(`${pathname}${href}`, { scroll: false });
  };
  
  return (
    <div className="min-h-screen bg-slate-950 text-slate-300">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col lg:flex-row">

          {/* Sidebar */}
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

          {/* Main Content */}
          <main className="w-full lg:pl-8 py-16">
            <div className="max-w-3xl mx-auto space-y-16">
              
              <section id="introduction">
                <h1 className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-pink-500 mb-4">Agent API Introduction</h1>
                <p className="text-lg text-slate-400">
                  The Jean Memory Agent API provides a robust, isolated, and easy-to-use memory layer for your AI applications. It's designed for production use cases where multiple AI agents need to collaborate by sharing a common context.
                </p>
                <div className="mt-6 p-4 border border-slate-800 rounded-lg bg-slate-900/50">
                  <h3 className="font-semibold text-slate-100 flex items-center"><Terminal className="w-5 h-5 mr-2 text-slate-400"/>What can you do with it?</h3>
                  <ul className="mt-2 ml-2 space-y-2 text-sm text-slate-400 list-disc list-inside">
                    <li>Give an agent swarm a shared "scratchpad" for collaboration.</li>
                    <li>Persist logs and findings from autonomous agents.</li>
                    <li>Isolate memory between different tasks using metadata tags.</li>
                    <li>Build complex workflows where one agent's output is another's input.</li>
                  </ul>
                </div>
              </section>

              <section id="authentication">
                <h2 className="text-3xl font-bold text-slate-100 mb-4">Authentication</h2>
                <p>All endpoints are protected. You need a <code className="text-sm font-mono bg-slate-800 px-1 rounded">Bearer Token</code> for your user account and an <code className="text-sm font-mono bg-slate-800 px-1 rounded">X-Client-Name</code> header to scope memories to a specific application or agent swarm.</p>
                <CodeBlock lang="http" code={`
Authorization: Bearer <YOUR_JWT_TOKEN>
X-Client-Name: <your-unique-app-name>
                `} />
              </section>

              <section id="endpoints">
                <h2 className="text-3xl font-bold text-slate-100 mb-4">API Endpoints</h2>
                <div className="space-y-10">
                  <div>
                    <h3 className="text-xl font-semibold text-slate-200">Add Tagged Memory</h3>
                    <p className="mt-1 text-slate-400">Adds a new memory with associated metadata tags.</p>
                    <div className="flex items-center gap-2 mt-3">
                      <span className="font-mono text-xs font-bold text-green-400 bg-green-900/50 px-2 py-1 rounded">POST</span>
                      <span className="font-mono text-sm text-slate-400">/agent/v1/memory/add_tagged</span>
                    </div>
                    <h4 className="font-semibold text-slate-300 mt-4 mb-2">Example Request:</h4>
                    <CodeBlock code={`
curl -X POST ${API_URL}/agent/v1/memory/add_tagged \\
  -H "Authorization: Bearer <YOUR_TOKEN>" \\
  -H "X-Client-Name: research_swarm_alpha" \\
  -d '{
    "text": "Fact: Mars is also known as the Red Planet.",
    "metadata": {"task_id": "mars_research_101"}
  }'
                    `} />
                  </div>
                  <div>
                    <h3 className="text-xl font-semibold text-slate-200">Search by Tags</h3>
                    <p className="mt-1 text-slate-400">Searches for memories matching all key-value pairs in the filter.</p>
                     <div className="flex items-center gap-2 mt-3">
                      <span className="font-mono text-xs font-bold text-green-400 bg-green-900/50 px-2 py-1 rounded">POST</span>
                      <span className="font-mono text-sm text-slate-400">/agent/v1/memory/search_by_tags</span>
                    </div>
                    <h4 className="font-semibold text-slate-300 mt-4 mb-2">Example Request:</h4>
                    <CodeBlock code={`
curl -X POST ${API_URL}/agent/v1/memory/search_by_tags \\
  -H "Authorization: Bearer <YOUR_TOKEN>" \\
  -H "X-Client-Name: research_swarm_alpha" \\
  -d '{"filter": {"task_id": "mars_research_101"}}'
                    `} />
                  </div>
                </div>
              </section>

              <section id="sdk">
                <h2 className="text-3xl font-bold text-slate-100 mb-4">Python SDK</h2>
                <p>For easier integration, we provide a Python client. It's located in the <code className="text-sm font-mono bg-slate-800 px-1 rounded">openmemory/sdk</code> directory of the repository.</p>
                <div className="mt-4 p-4 border border-slate-800 rounded-lg bg-slate-900/50 text-sm">
                  <div className="flex items-center text-amber-300"><DownloadCloud className="w-4 h-4 mr-2"/>Note on Installation</div>
                  <p className="text-slate-400 mt-1">To use the SDK, you don't need to install it from a package manager. Simply copy the <code className="text-xs font-mono bg-slate-800 px-1 rounded">openmemory/sdk</code> directory into your project or add it to your Python path.</p>
                </div>
                <h4 className="font-semibold text-slate-300 mt-6 mb-2">Example Usage:</h4>
                <CodeBlock lang="python" code={`
from openmemory.sdk.client import JeanMemoryClient

# Reads JEAN_API_TOKEN from environment variables
client = JeanMemoryClient()

# Add a memory, scoped to your app
client.add_tagged_memory(
    text="This is a finding from our research agent.",
    metadata={"task_id": "koii_task_123"},
    client_name="koii_swarm_app"
)

# Retrieve memories for that task
memories = client.search_by_tags(
    filters={"task_id": "koii_task_123"},
    client_name="koii_swarm_app"
)
print(memories)
                `} />
              </section>

              <section id="example">
                <h2 className="text-3xl font-bold text-slate-100 mb-4">Example: Agent Collaboration</h2>
                <p>This example demonstrates a common pattern where a <strong className="text-slate-200">Researcher</strong> agent gathers information, and a <strong className="text-slate-200">Summarizer</strong> agent processes it. Both agents use the same <code className="text-sm font-mono bg-slate-800 px-1 rounded">task_id</code> to share context.</p>

                <h4 className="font-semibold text-slate-300 mt-6 mb-2">1. Researcher Agent</h4>
                <p className="text-sm text-slate-400 mb-2">This agent discovers facts on a topic and stores them as individual memories tagged with the task ID.</p>
                <CodeBlock lang="python" code={`
import os
from openmemory.sdk.client import JeanMemoryClient

def research_agent(task_id: str, topic: str):
    """Agent 1: Discovers facts and adds them to memory."""
    print(f"--- [Research Agent] discovering facts about '{topic}' ---")
    
    # In a real scenario, this would come from a web search or document analysis
    facts = [
        f"{topic} are a type of flowering plant in the nightshade family Solanaceae.",
        "The tomato is the edible berry of the plant Solanum lycopersicum.",
        "Tomatoes are a significant source of umami flavor.",
    ]
    
    client = JeanMemoryClient()
    for i, fact in enumerate(facts):
        metadata = {"task_id": task_id, "type": "fact", "step": i + 1}
        client.add_tagged_memory(text=fact, metadata=metadata, client_name="collaboration_app")
        print(f"  - Added fact #{i+1}")

    print("--- ✅ Research complete ---")
                `} />

                <h4 className="font-semibold text-slate-300 mt-6 mb-2">2. Summarizer Agent</h4>
                <p className="text-sm text-slate-400 mb-2">After the researcher is done, this agent retrieves all the facts for the task, uses an LLM to create a summary, and stores the final result back into memory.</p>
                <CodeBlock lang="python" code={`
import os
import time
from openai import OpenAI
from openmemory.sdk.client import JeanMemoryClient

def summarizer_agent(task_id: str, topic: str):
    """Agent 2: Finds facts, uses an LLM to summarize, and stores the summary."""
    print(f"--- [Summarizer Agent] creating a summary for '{topic}' ---")
    
    client = JeanMemoryClient()
    llm_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    # Search for all facts related to this specific task
    time.sleep(1) # Give a moment for DB to be consistent
    facts = client.search_by_tags(
        filters={"task_id": task_id, "type": "fact"},
        client_name="collaboration_app"
    )
    
    if not facts:
        print("--- ❌ ERROR: No facts found to summarize. ---")
        return

    # Prepare context for the LLM
    fact_list = "\\n".join([f"- {mem.get('content', '')}" for mem in facts])
    prompt = f"Please synthesize the following facts about {topic} into a single, concise paragraph:\\n\\n{fact_list}"
    
    # Generate summary
    response = llm_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    summary = response.choices[0].message.content
    
    # Store the final product
    metadata = {"task_id": task_id, "type": "summary"}
    client.add_tagged_memory(text=summary, metadata=metadata, client_name="collaboration_app")

    print("--- ✅ Summary complete and stored ---")
                `} />

              </section>

            </div>
          </main>
        </div>
      </div>
    </div>
  );
};

export default DocsPage; 