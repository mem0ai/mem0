"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useState } from "react";
import { Brain, ExternalLink, MessageCircle, Sparkles, ArrowRight, CheckCircle, Terminal, Copy, ChevronDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export default function SetupMCPPage() {
  const [supportForm, setSupportForm] = useState({
    name: '',
    email: '',
    message: ''
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [copiedItem, setCopiedItem] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleSupportSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    
    try {
      const response = await fetch('/api/support', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(supportForm),
      });

      if (!response.ok) {
        throw new Error('Failed to send support request');
      }

      setIsSubmitted(true);
      setSupportForm({ name: '', email: '', message: '' });
    } catch (error) {
      console.error('Error submitting support request:', error);
      // You could add error state here if needed
      alert('Failed to send message. Please try again or email politzki18@gmail.com directly.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const copyToClipboard = (text: string, item: string) => {
    navigator.clipboard.writeText(text);
    setCopiedItem(item);
    setTimeout(() => setCopiedItem(null), 2000);
  };

  return (
    <div className="container mx-auto max-w-4xl px-4 py-8">
      <div className="space-y-8">
        {/* Header */}
        <div className="text-center space-y-4">
          <h1 className="text-4xl font-bold flex items-center justify-center gap-3">
            <Brain className="h-10 w-10 text-purple-500" />
            How to Use Jean Memory
          </h1>
          <p className="text-xl text-zinc-400">
            Connect your personal memory to any AI assistant in seconds
          </p>
          <div className="flex justify-center gap-2">
            <Badge variant="secondary">One Simple Command</Badge>
            <Badge variant="secondary">Works Everywhere</Badge>
          </div>
        </div>

        {/* Video Tutorial */}
        <Card className="border-blue-500/20 bg-gradient-to-r from-blue-500/5 to-purple-500/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-2xl">
              <svg className="h-6 w-6 text-red-500" viewBox="0 0 24 24" fill="currentColor">
                <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136C4.495 20.455 12 20.455 12 20.455s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
              </svg>
              Video Tutorial: Set Up Jean Memory in 5 Minutes
            </CardTitle>
            <CardDescription>
              Watch this step-by-step video tutorial to get Jean Memory working with your AI tools quickly and easily.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="relative w-full" style={{ paddingBottom: '56.25%' }}>
                <iframe
                  className="absolute top-0 left-0 w-full h-full rounded-lg"
                  src="https://www.youtube.com/embed/qXe4mEaCN9k"
                  title="Jean Memory Setup Tutorial"
                  frameBorder="0"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                  allowFullScreen
                ></iframe>
              </div>
              <div className="flex items-center gap-4 text-sm text-zinc-400">
                <span>⏱️ 5 minutes</span>
                <span>👨‍💻 Beginner-friendly</span>
                <span>🎯 Complete walkthrough</span>
              </div>
              <Alert className="border-blue-500/20 bg-blue-50 dark:bg-blue-950/20">
                <Sparkles className="h-4 w-4 text-blue-600" />
                <AlertDescription className="text-blue-800 dark:text-blue-200">
                  <strong>Perfect for beginners!</strong> This video covers everything from installing Node.js to testing your first memory. Follow along and you'll be up and running in minutes.
                </AlertDescription>
              </Alert>
            </div>
          </CardContent>
        </Card>

        {/* What This Does */}
        <Card className="border-purple-500/20">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-purple-500" />
              What This Does for You
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4">
              <div className="flex items-start gap-3">
                <CheckCircle className="h-5 w-5 text-green-500 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="font-medium">Your AI remembers everything about you</p>
                  <p className="text-sm text-zinc-400">Personal preferences, work history, goals, and important details</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <CheckCircle className="h-5 w-5 text-green-500 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="font-medium">Just talk naturally</p>
                  <p className="text-sm text-zinc-400">Say things like "Remember that I'm allergic to shellfish" or "What did I write about innovation?"</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <CheckCircle className="h-5 w-5 text-green-500 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="font-medium">Smarter conversations</p>
                  <p className="text-sm text-zinc-400">Your AI gives more personalized and relevant responses based on what it knows about you</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Simple Installation */}
        <Card className="border-green-500/20">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Terminal className="h-5 w-5 text-green-500" />
              Installation (30 seconds)
            </CardTitle>
            <CardDescription>
              Get your personalized install commands from your dashboard
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-3">
              <div className="bg-slate-50 dark:bg-slate-800/50 p-6 rounded-xl shadow-sm">
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-8 h-8 bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 rounded-full flex items-center justify-center text-sm font-semibold">
                    1
                  </div>
                  <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Sign up for Jean Memory</h3>
                </div>
                <p className="text-slate-600 dark:text-slate-300 ml-11">
                  Create your account at <a href="/auth" className="text-blue-600 dark:text-blue-400 hover:underline font-medium">jeanmemory.com</a> to get started
                </p>
              </div>

              <div className="bg-slate-50 dark:bg-slate-800/50 p-6 rounded-xl shadow-sm">
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-8 h-8 bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300 rounded-full flex items-center justify-center text-sm font-semibold">
                    2
                  </div>
                  <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Find your install commands</h3>
                </div>
                <p className="text-slate-600 dark:text-slate-300 ml-11">
                  Visit your <a href="/dashboard" className="text-blue-600 dark:text-blue-400 hover:underline font-medium">dashboard</a> and look for the "Quick Setup" section with personalized commands
                </p>
              </div>

              <div className="bg-slate-50 dark:bg-slate-800/50 p-6 rounded-xl shadow-sm">
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-8 h-8 bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300 rounded-full flex items-center justify-center text-sm font-semibold">
                    3
                  </div>
                  <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Copy your personalized command</h3>
                </div>
                <p className="text-slate-600 dark:text-slate-300 ml-11">
                  Click on your AI app (Claude, Cursor, etc.) - the command already has your unique user ID filled in automatically
                </p>
              </div>

              <div className="bg-slate-50 dark:bg-slate-800/50 p-6 rounded-xl shadow-sm">
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-8 h-8 bg-orange-100 dark:bg-orange-900/50 text-orange-700 dark:text-orange-300 rounded-full flex items-center justify-center text-sm font-semibold">
                    4
                  </div>
                  <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Run the command & restart</h3>
                </div>
                <div className="ml-11 space-y-2">
                  <p className="text-slate-600 dark:text-slate-300">
                    Paste the command in your terminal and follow the prompts
                  </p>
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    Then restart your AI app completely (quit and reopen) - that's it!
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Troubleshooting */}
        <Card className="border-orange-500/20">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <svg className="h-5 w-5 text-orange-500" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
              </svg>
              Troubleshooting
            </CardTitle>
            <CardDescription>
              Having trouble with the install command? Here are common fixes
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Alert className="border-orange-500/20 bg-orange-50 dark:bg-orange-950/20">
              <Terminal className="h-4 w-4 text-orange-600" />
              <AlertDescription className="text-orange-800 dark:text-orange-200">
                <div className="space-y-3">
                  <div>
                    <strong>Error: "Cannot find module 'yargs'" on Mac?</strong>
                    <p className="text-sm mt-1">This is a common NPX cache issue. Try these commands:</p>
                  </div>
                  
                  <div className="bg-zinc-900 p-3 rounded font-mono text-sm">
                    <div className="text-green-400 mb-1">1. Install yargs globally:</div>
                    <div className="text-zinc-300">npm install -g yargs</div>
                    
                    <div className="text-green-400 mb-1 mt-3">2. Clear NPX cache:</div>
                    <div className="text-zinc-300">npx clear-npx-cache</div>
                    
                    <div className="text-green-400 mb-1 mt-3">3. Try install command again:</div>
                    <div className="text-zinc-300">npx install-mcp https://api.jeanmemory.com/mcp/...</div>
                  </div>
                  
                  <p className="text-xs text-orange-700 dark:text-orange-300">
                    This fixes dependency resolution issues with NPX on some Mac systems.
                  </p>
                </div>
              </AlertDescription>
            </Alert>
            
            <div className="grid gap-3 text-sm">
              <div className="flex items-start gap-2">
                <CheckCircle className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                <div>
                  <strong>Node.js not found?</strong> Install from <a href="https://nodejs.org" className="text-blue-600 hover:underline">nodejs.org</a>
                </div>
              </div>
              <div className="flex items-start gap-2">
                <CheckCircle className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                <div>
                  <strong>Permission denied?</strong> Try adding <code className="bg-zinc-200 dark:bg-zinc-800 px-1 rounded">sudo</code> before the command
                </div>
              </div>
              <div className="flex items-start gap-2">
                <CheckCircle className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                <div>
                  <strong>Command not working?</strong> Make sure you copied the full command from your dashboard
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Example Conversations */}
        <Card>
          <CardHeader>
            <CardTitle>Example Conversations</CardTitle>
            <CardDescription>
              Here's how you'll talk to your AI assistant once connected
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="bg-zinc-900 p-4 rounded-lg">
                <p className="text-green-400 text-sm mb-1">You:</p>
                <p className="mb-3">"Remember that I prefer TypeScript over JavaScript for new projects"</p>
                <p className="text-blue-400 text-sm mb-1">AI:</p>
                <p className="text-sm text-zinc-300">✓ I'll remember your preference for TypeScript. This will help me give better coding advice!</p>
              </div>
              
              <div className="bg-zinc-900 p-4 rounded-lg">
                <p className="text-green-400 text-sm mb-1">You:</p>
                <p className="mb-3">"What did I write about innovation in my essays?"</p>
                <p className="text-blue-400 text-sm mb-1">AI:</p>
                <p className="text-sm text-zinc-300">Based on your essay "The Irreverent Act," you wrote about innovation requiring irreverence and challenging the status quo...</p>
              </div>

              <div className="bg-zinc-900 p-4 rounded-lg">
                <p className="text-green-400 text-sm mb-1">You:</p>
                <p className="mb-3">"Help me write a blog post about entrepreneurship"</p>
                <p className="text-blue-400 text-sm mb-1">AI:</p>
                <p className="text-sm text-zinc-300">I'll help you write that! Based on your previous writing about irreverence and 0-1 innovation, I'll make sure it reflects your unique perspective...</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Advanced Section */}
        <Card className="border-violet-500/20">
          <CardHeader 
            className="cursor-pointer" 
            onClick={() => setShowAdvanced(!showAdvanced)}
          >
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <svg className="h-5 w-5 text-violet-500" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19.14,12.94c0.04-0.3,0.06-0.61,0.06-0.94c0-0.32-0.02-0.64-0.07-0.94l2.03-1.58c0.18-0.14,0.23-0.41,0.12-0.61 l-1.92-3.32c-0.12-0.22-0.37-0.29-0.59-0.22l-2.39,0.96c-0.5-0.38-1.03-0.7-1.62-0.94L14.4,2.81c-0.04-0.24-0.24-0.41-0.48-0.41 h-3.84c-0.24,0-0.43,0.17-0.47,0.41L9.25,5.35C8.66,5.59,8.12,5.92,7.63,6.29L5.24,5.33c-0.22-0.08-0.47,0-0.59,0.22L2.74,8.87 C2.62,9.08,2.66,9.34,2.86,9.48l2.03,1.58C4.84,11.36,4.8,11.69,4.8,12s0.02,0.64,0.07,0.94l-2.03,1.58 c-0.18,0.14-0.23,0.41-0.12,0.61l1.92,3.32c0.12,0.22,0.37,0.29,0.59,0.22l2.39-0.96c0.5,0.38,1.03,0.7,1.62,0.94l0.36,2.54 c0.05,0.24,0.24,0.41,0.48,0.41h3.84c0.24,0,0.44-0.17,0.47-0.41l0.36-2.54c0.59-0.24,1.13-0.56,1.62-0.94l2.39,0.96 c0.22,0.08,0.47,0,0.59-0.22l1.92-3.32c0.12-0.22,0.07-0.47-0.12-0.61L19.14,12.94z M12,15.6c-1.98,0-3.6-1.62-3.6-3.6 s1.62-3.6,3.6-3.6s3.6,1.62,3.6,3.6S13.98,15.6,12,15.6z"/>
                </svg>
                Advanced Configuration
              </div>
              <ChevronDown className={`h-5 w-5 text-violet-500 transition-transform ${showAdvanced ? 'rotate-180' : ''}`} />
            </CardTitle>
            <CardDescription>
              Power user tips, system prompts, and advanced settings
            </CardDescription>
          </CardHeader>
          
          {showAdvanced && (
            <CardContent className="space-y-6">
              {/* System Prompts */}
              <div className="space-y-3">
                <h4 className="font-semibold text-violet-400 flex items-center gap-2">
                  <Terminal className="h-4 w-4" />
                  Custom System Prompts
                </h4>
                <p className="text-sm text-zinc-400">
                  Enhance your AI assistant with custom system prompts that integrate Jean Memory:
                </p>
                <div className="bg-zinc-900 p-4 rounded-lg">
                  <div className="text-xs text-zinc-500 mb-2">Add this to your Claude system prompt:</div>
                  <div className="bg-zinc-800 p-3 rounded text-sm font-mono text-zinc-300">
                    "You have access to Jean Memory tools. Always search my memory for relevant context before answering questions. When I share important information, offer to remember it for future conversations."
                  </div>
                  <button 
                    onClick={() => copyToClipboard("You have access to Jean Memory tools. Always search my memory for relevant context before answering questions. When I share important information, offer to remember it for future conversations.", "system-prompt")}
                    className="mt-2 text-xs text-violet-400 hover:text-violet-300 flex items-center gap-1"
                  >
                    <Copy className="h-3 w-3" />
                    {copiedItem === "system-prompt" ? "Copied!" : "Copy"}
                  </button>
                </div>
              </div>

              {/* Multiple Clients */}
              <div className="space-y-3">
                <h4 className="font-semibold text-violet-400 flex items-center gap-2">
                  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-1 9h-4v4h-2v-4H9V9h4V5h2v4h4v2z"/>
                  </svg>
                  Multiple AI Apps
                </h4>
                <p className="text-sm text-zinc-400">
                  Connect the same memory to multiple AI applications:
                </p>
                <div className="grid gap-2 text-sm">
                  <div className="bg-zinc-800/50 p-3 rounded">
                    <strong className="text-green-400">Claude:</strong>
                    <code className="ml-2 text-xs">npx install-mcp https://api.jeanmemory.com/mcp/claude/sse/YOUR_ID --client claude</code>
                  </div>
                  <div className="bg-zinc-800/50 p-3 rounded">
                    <strong className="text-blue-400">Cursor:</strong>
                    <code className="ml-2 text-xs">npx install-mcp https://api.jeanmemory.com/mcp/cursor/sse/YOUR_ID --client cursor</code>
                  </div>
                  <div className="bg-zinc-800/50 p-3 rounded">
                    <strong className="text-purple-400">Windsurf:</strong>
                    <code className="ml-2 text-xs">npx install-mcp https://api.jeanmemory.com/mcp/windsurf/sse/YOUR_ID --client windsurf</code>
                  </div>
                </div>
              </div>

              {/* Memory Organization */}
              <div className="space-y-3">
                <h4 className="font-semibold text-violet-400 flex items-center gap-2">
                  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M10 4H4c-1.1 0-2 .9-2 2v3h2V6h6V4zm6 0v2h6v3h2V6c0-1.1-.9-2-2-2h-6zm-6 15H4v-3H2v3c0 1.1.9 2 2 2h6v-2zm6 2h6c1.1 0 2-.9 2-2v-3h-2v3h-6v2zm-3-7.5c-1.38 0-2.5 1.12-2.5 2.5s1.12 2.5 2.5 2.5 2.5-1.12 2.5-2.5-1.12-2.5-2.5-2.5z"/>
                  </svg>
                  Memory Organization Tips
                </h4>
                <div className="space-y-2 text-sm text-zinc-400">
                  <div className="flex items-start gap-2">
                    <CheckCircle className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                    <div>
                      <strong>Be specific:</strong> Instead of "I like coffee", say "I prefer dark roast coffee, no sugar, oat milk"
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <CheckCircle className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                    <div>
                      <strong>Include context:</strong> "For my startup project X, I'm using TypeScript and Supabase"
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <CheckCircle className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                    <div>
                      <strong>Update regularly:</strong> "Actually, I switched from React to Next.js for better SEO"
                    </div>
                  </div>
                </div>
              </div>

              {/* API Access */}
              <div className="space-y-3">
                <h4 className="font-semibold text-violet-400 flex items-center gap-2">
                  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M8.5,18l3.5,4l3.5-4H19c1.1,0,2-0.9,2-2V4c0-1.1-0.9-2-2-2H5C3.9,2,3,2.9,3,4v12c0,1.1,0.9,2,2,2H8.5z M7,7h10v2H7V7z M7,11h8v2H7V11z"/>
                  </svg>
                  Direct API Access
                </h4>
                <p className="text-sm text-zinc-400">
                  For developers: Access your memories programmatically
                </p>
                <div className="bg-zinc-900 p-4 rounded-lg">
                  <div className="text-xs text-zinc-500 mb-2">API Documentation:</div>
                  <a 
                    href="https://api.jeanmemory.com/docs" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-violet-400 hover:text-violet-300 text-sm flex items-center gap-1"
                  >
                    <ExternalLink className="h-3 w-3" />
                    api.jeanmemory.com/docs
                  </a>
                </div>
              </div>
            </CardContent>
          )}
        </Card>

        {/* Support */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MessageCircle className="h-5 w-5" />
              Need Help?
            </CardTitle>
            <CardDescription>
              Get help from the community or contact us directly
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Discord Community */}
            <div className="bg-gradient-to-r from-indigo-500/10 to-purple-500/10 border border-indigo-500/20 rounded-lg p-4">
              <div className="flex items-center gap-3 mb-3">
                <svg className="h-6 w-6 text-indigo-400" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419-.0189 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1568 2.4189Z"/>
                </svg>
                <div>
                  <h4 className="font-semibold text-indigo-300">Join Our Discord Community</h4>
                  <p className="text-sm text-indigo-200/80">Get instant help, share setups, and connect with other Jean Memory users</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <a
                  href="https://discord.gg/NYru6Wbr"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center"
                >
                  <Button className="bg-indigo-600 hover:bg-indigo-700 text-white flex items-center gap-2">
                    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419-.0189 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1568 2.4189Z"/>
                    </svg>
                    Join Discord
                  </Button>
                </a>
                <div className="text-xs text-indigo-300/70">
                  💬 Live chat • 🛠️ Setup help • 🚀 Feature updates
                </div>
              </div>
            </div>

            <div className="text-center text-sm text-zinc-500">
              <strong>Need one-on-one help?</strong> Send us a message below and we'll get back to you within 24 hours.
            </div>

            {/* Support Form */}
            {isSubmitted ? (
              <div className="text-center py-8">
                <CheckCircle className="h-12 w-12 text-green-500 mx-auto mb-4" />
                <h3 className="text-lg font-semibold mb-2">Message Sent!</h3>
                <p className="text-zinc-400">We'll get back to you within 24 hours.</p>
              </div>
            ) : (
              <form onSubmit={handleSupportSubmit} className="space-y-4">
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium mb-1 block">Name</label>
                    <Input
                      value={supportForm.name}
                      onChange={(e) => setSupportForm({...supportForm, name: e.target.value})}
                      placeholder="Your name"
                      required
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium mb-1 block">Email</label>
                    <Input
                      type="email"
                      value={supportForm.email}
                      onChange={(e) => setSupportForm({...supportForm, email: e.target.value})}
                      placeholder="your@email.com"
                      required
                    />
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium mb-1 block">How can we help?</label>
                  <Textarea
                    value={supportForm.message}
                    onChange={(e) => setSupportForm({...supportForm, message: e.target.value})}
                    placeholder="I can't find Jean Memory in Claude Desktop..."
                    className="min-h-[100px]"
                    required
                  />
                </div>
                <Button type="submit" disabled={isSubmitting} className="w-full">
                  {isSubmitting ? "Sending..." : "Send Message"}
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
              </form>
            )}
          </CardContent>
        </Card>

        {/* Bottom CTA */}
        <Alert>
          <Sparkles className="h-4 w-4" />
          <AlertDescription>
            <strong>Ready to get started?</strong> Copy the command above, paste it in your terminal, and restart your AI app. Jean Memory will be waiting for you!
          </AlertDescription>
        </Alert>
      </div>
    </div>
  );
} 