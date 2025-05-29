"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { Check, Copy, Terminal, Brain, Sparkles, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export default function SetupMCPPage() {
  const [copiedItem, setCopiedItem] = useState<string | null>(null);

  const copyToClipboard = (text: string, item: string) => {
    navigator.clipboard.writeText(text);
    setCopiedItem(item);
    setTimeout(() => setCopiedItem(null), 2000);
  };

  const CodeBlock = ({ code, item }: { code: string; item: string }) => (
    <div className="relative">
      <pre className="bg-zinc-900 p-4 rounded-lg overflow-x-auto">
        <code className="text-zinc-100 text-sm">{code}</code>
      </pre>
      <Button
        size="sm"
        variant="ghost"
        className="absolute top-2 right-2"
        onClick={() => copyToClipboard(code, item)}
      >
        {copiedItem === item ? (
          <Check className="h-4 w-4 text-green-500" />
        ) : (
          <Copy className="h-4 w-4" />
        )}
      </Button>
    </div>
  );

  return (
    <div className="container mx-auto max-w-4xl px-4 py-8">
      <div className="space-y-8">
        {/* Header */}
        <div className="text-center space-y-4">
          <h1 className="text-4xl font-bold flex items-center justify-center gap-3">
            <Brain className="h-10 w-10 text-purple-500" />
            Jean Memory MCP Setup
          </h1>
          <p className="text-lg text-zinc-400">
            Connect your memory to Claude Desktop or Cursor for AI-powered memory assistance
          </p>
          <div className="flex justify-center gap-2">
            <Badge variant="secondary">Claude Desktop</Badge>
            <Badge variant="secondary">Cursor IDE</Badge>
            <Badge variant="secondary">Model Context Protocol</Badge>
          </div>
        </div>

        {/* Prerequisites Alert */}
        <Alert>
          <Sparkles className="h-4 w-4" />
          <AlertDescription>
            <strong>Prerequisites:</strong> Make sure you have Node.js 18+ installed and either Claude Desktop or Cursor IDE
          </AlertDescription>
        </Alert>

        {/* Installation Tabs */}
        <Tabs defaultValue="claude" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="claude">Claude Desktop</TabsTrigger>
            <TabsTrigger value="cursor">Cursor IDE</TabsTrigger>
          </TabsList>

          <TabsContent value="claude" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Installing Jean Memory for Claude Desktop</CardTitle>
                <CardDescription>
                  Follow these steps to connect your memory to Claude Desktop
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <h3 className="font-semibold mb-2">1. Install the MCP Server</h3>
                  <CodeBlock 
                    code="npx @openmemory/mcp-server claude"
                    item="claude-install"
                  />
                  <p className="text-sm text-zinc-400 mt-2">
                    This will automatically configure Claude Desktop to use Jean Memory
                  </p>
                </div>

                <div>
                  <h3 className="font-semibold mb-2">2. Restart Claude Desktop</h3>
                  <p className="text-sm text-zinc-400">
                    Quit and reopen Claude Desktop to load the new configuration
                  </p>
                </div>

                <div>
                  <h3 className="font-semibold mb-2">3. Verify Connection</h3>
                  <p className="text-sm text-zinc-400">
                    In Claude, you should see "jean-memory-api" in the MCP tools menu
                  </p>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="cursor" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Installing Jean Memory for Cursor</CardTitle>
                <CardDescription>
                  Follow these steps to connect your memory to Cursor IDE
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <h3 className="font-semibold mb-2">1. Install the MCP Server</h3>
                  <CodeBlock 
                    code="npx @openmemory/mcp-server cursor"
                    item="cursor-install"
                  />
                  <p className="text-sm text-zinc-400 mt-2">
                    This will automatically configure Cursor to use Jean Memory
                  </p>
                </div>

                <div>
                  <h3 className="font-semibold mb-2">2. Restart Cursor</h3>
                  <p className="text-sm text-zinc-400">
                    Quit and reopen Cursor to load the new configuration
                  </p>
                </div>

                <div>
                  <h3 className="font-semibold mb-2">3. Verify Connection</h3>
                  <p className="text-sm text-zinc-400">
                    In Cursor's AI chat, you should see Jean Memory tools available
                  </p>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Available Tools */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Terminal className="h-5 w-5" />
              Available Memory Tools
            </CardTitle>
            <CardDescription>
              These tools will be available in your AI assistant
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4">
              <div className="space-y-2">
                <div className="flex items-start gap-3">
                  <Badge className="mt-1">add_memories</Badge>
                  <div>
                    <p className="font-medium">Add Memory</p>
                    <p className="text-sm text-zinc-400">
                      Save important information, facts, or observations to your memory
                    </p>
                    <CodeBlock 
                      code='Example: "Remember that I prefer TypeScript over JavaScript for all new projects"'
                      item="add-example"
                    />
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-start gap-3">
                  <Badge className="mt-1">search_memory</Badge>
                  <div>
                    <p className="font-medium">Search Memory</p>
                    <p className="text-sm text-zinc-400">
                      Search your memories for specific information
                    </p>
                    <CodeBlock 
                      code='Example: "What do I think about irreverence?"'
                      item="search-example"
                    />
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-start gap-3">
                  <Badge className="mt-1">deep_memory_query</Badge>
                  <div>
                    <p className="font-medium">Deep Memory Query</p>
                    <p className="text-sm text-zinc-400">
                      Comprehensive analysis across all your documents and memories
                    </p>
                    <CodeBlock 
                      code='Example: "Analyze my philosophy on innovation from my essays"'
                      item="deep-example"
                    />
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-start gap-3">
                  <Badge className="mt-1">smart_memory_query</Badge>
                  <div>
                    <p className="font-medium">Smart Memory Query</p>
                    <p className="text-sm text-zinc-400">
                      Two-layer fast search using Gemini 2.5 models for complex queries
                    </p>
                    <CodeBlock 
                      code='Example: "Find connections between my thoughts on AI and entrepreneurship"'
                      item="smart-example"
                    />
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-start gap-3">
                  <Badge className="mt-1">sync_substack_posts</Badge>
                  <div>
                    <p className="font-medium">Sync Substack</p>
                    <p className="text-sm text-zinc-400">
                      Import your Substack posts into your memory
                    </p>
                    <CodeBlock 
                      code='Example: "Sync my Substack from https://yourname.substack.com"'
                      item="sync-example"
                    />
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Usage Tips */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5" />
              Pro Tips
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-start gap-2">
              <span className="text-purple-500">•</span>
              <p className="text-sm">
                <strong>Performance:</strong> Regular search is instant, deep queries take 30-60 seconds but provide comprehensive insights
              </p>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-purple-500">•</span>
              <p className="text-sm">
                <strong>Memory Building:</strong> The more you add to your memory, the more valuable it becomes over time
              </p>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-purple-500">•</span>
              <p className="text-sm">
                <strong>Document Chunking:</strong> Run chunk_documents after syncing to improve search performance
              </p>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-purple-500">•</span>
              <p className="text-sm">
                <strong>Context Aware:</strong> Your AI assistant will have access to your entire knowledge base for more personalized help
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Troubleshooting */}
        <Card>
          <CardHeader>
            <CardTitle>Troubleshooting</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <p className="font-medium text-sm">Tools not showing up?</p>
              <p className="text-sm text-zinc-400">
                Make sure you've restarted Claude/Cursor after installation
              </p>
            </div>
            <div>
              <p className="font-medium text-sm">Connection errors?</p>
              <p className="text-sm text-zinc-400">
                Check that you're logged into Jean Memory and have an active API connection
              </p>
            </div>
            <div>
              <p className="font-medium text-sm">Slow queries?</p>
              <p className="text-sm text-zinc-400">
                Deep queries process all your content - use regular search for quick lookups
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
} 