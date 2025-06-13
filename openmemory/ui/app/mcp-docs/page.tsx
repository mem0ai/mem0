"use client";

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Copy, Check } from 'lucide-react';
import { useRouter } from 'next/navigation';

// --- Reusable Components ---
const CodeBlock = ({ code, lang }: { code: string, lang?: string }) => {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(code.trim());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group my-4 bg-slate-900 rounded-lg border border-slate-700/50 shadow-lg">
       <div className="flex text-xs text-slate-400 border-b border-slate-700/50">
        <div className="px-4 py-2 ">{lang?.toUpperCase()}</div>
      </div>
      <pre className="p-4 text-sm font-mono overflow-x-auto text-slate-200 whitespace-pre-wrap">
        <code>{code.trim()}</code>
      </pre>
      <button
        onClick={handleCopy}
        className="absolute top-10 right-2 p-2 rounded-md bg-slate-800/50 hover:bg-slate-700 transition-colors opacity-0 group-hover:opacity-100"
        aria-label="Copy code"
      >
        {copied ? <Check className="h-4 w-4 text-green-400" /> : <Copy className="h-4 w-4 text-slate-400" />}
      </button>
    </div>
  );
};

const DocsHeader = ({ title, subtitle }: { title: string, subtitle: string }) => (
    <section>
        <h1 className="text-3xl font-bold text-slate-100 mb-2">{title}</h1>
        <p className="text-lg text-slate-400">{subtitle}</p>
    </section>
);

const DocsSection = ({ id, title, children }: { id: string, title: string, children: React.ReactNode }) => (
    <section id={id} className="pt-10">
        <h2 className="text-xl font-semibold text-slate-200 mb-4 pb-2 border-b border-slate-800">{title}</h2>
        <div className="space-y-4 text-slate-300">{children}</div>
    </section>
);


// --- Main Page Component ---
const MCPDocsPage = () => {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  
  // --- Auth Logic ---
  useEffect(() => {
    if (!isLoading && !user) router.push('/auth');
  }, [user, isLoading, router]);

  if (isLoading || !user) {
    return <div className="min-h-screen bg-slate-950 flex items-center justify-center text-white">Loading...</div>;
  }

  const mcpUrl = `https://api.jeanmemory.com/mcp/claude/sse/${user.id}`;
  const restApiUrl = `https://api.jeanmemory.com/api/v1/mcp/search_memory`;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-300">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto py-16">
            <div className="space-y-12">
              
                <DocsHeader title="Agent Integration Guide" subtitle="How to connect AI agents and custom applications to Jean Memory." />

                <DocsSection id="connection-methods" title="Connection Methods">
                    <p>There are two ways to connect to Jean Memory, depending on your use case.</p>
                    <ul className="list-disc pl-5 space-y-2">
                        <li>
                            <strong className="text-slate-200">MCP for Compatible Agents:</strong> For agents that support the Model Context Protocol (like the Claude desktop app), use the `install-mcp` command. This is the simplest method for pre-built agents.
                        </li>
                        <li>
                            <strong className="text-slate-200">REST API for Custom Scripts:</strong> To build a new agent from scratch or integrate with a custom application, use the standard REST API. This method is universal and works with any programming language.
                        </li>
                    </ul>
                </DocsSection>

                <DocsSection id="mcp-agents" title="Method 1: Connecting an MCP-Compatible Agent">
                    <p>This method configures an existing, compatible agent (e.g., Claude) to use your memory. It will not work for custom Python scripts.</p>
                    <h3 className="font-semibold text-slate-200 pt-4">Your Personalized Install Command:</h3>
                    <p>Run the following command in your terminal. It includes your unique User ID and will configure your local MCP client.</p>
                    <CodeBlock code={`npx install-mcp ${mcpUrl} --client claude`} lang="bash" />
                    <p>Once installed, the agent will automatically discover and be able to use your memory tools.</p>
                </DocsSection>

                <DocsSection id="rest-api" title="Method 2: Integrating a Custom Script via REST API">
                    <p>This is the correct method for building a new agent from scratch in any language.</p>
                    <h3 className="font-semibold text-slate-200 pt-4">Step 1: Get Your JWT Token</h3>
                    <p>To authenticate with the REST API, you need a JSON Web Token. You can get this by logging into the Jean Memory web app, opening your browser's developer tools, and copying the `Bearer Token` from the `Authorization` header of any API request.</p>
                    <CodeBlock code={`# Your JWT will be a very long string, e.g.:
"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."`} lang="text" />
                    
                    <h3 className="font-semibold text-slate-200 pt-4">Step 2: Make API Calls</h3>
                    <p>You can now make standard HTTP requests to the API endpoints. The example below shows how to search memory using Python and the `requests` library.</p>
                    <CodeBlock code={`import requests
import json

# Your unique values
API_URL = "${restApiUrl}"
JWT_TOKEN = "YOUR_JWT_TOKEN" # Replace with your actual token
CLIENT_NAME = "my-custom-python-agent" # A name for your agent

def search_memory(query: str):
    headers = {
        "Authorization": f"Bearer {JWT_TOKEN}",
        "Content-Type": "application/json",
        "X-Client-Name": CLIENT_NAME
    }
    payload = {"query": query}

    try:
        response = requests.post(API_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status() # Raises an error for bad responses (4xx or 5xx)
        
        print("✅ Search successful!")
        print(json.dumps(response.json(), indent=2))

    except requests.exceptions.HTTPError as err:
        print(f"❌ HTTP Error: {err}")
        print(f"   Response Body: {err.response.text}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    search_memory("what is the user's project code?")`} lang="python" />
                    <h3 className="font-semibold text-slate-200 pt-4">Available REST Endpoints</h3>
                    <p>You can use the same pattern to call other tools:</p>
                    <ul className="list-disc pl-5 space-y-1 font-mono text-sm">
                        <li>`POST /api/v1/mcp/add_memories`</li>
                        <li>`POST /api/v1/mcp/list_memories`</li>
                    </ul>
                </DocsSection>
            </div>
        </div>
      </div>
    </div>
  );
};

export default MCPDocsPage; 