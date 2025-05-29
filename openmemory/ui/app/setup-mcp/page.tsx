"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useState } from "react";
import { Brain, ExternalLink, MessageCircle, Sparkles, ArrowRight, CheckCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export default function SetupMCPPage() {
  const [supportForm, setSupportForm] = useState({
    name: '',
    email: '',
    message: ''
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);

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
      alert('Failed to send message. Please try again or email jonathan@jeantechnologies.com directly.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="container mx-auto max-w-4xl px-4 py-8">
      <div className="space-y-8">
        {/* Header */}
        <div className="text-center space-y-4">
          <h1 className="text-4xl font-bold flex items-center justify-center gap-3">
            <Brain className="h-10 w-10 text-purple-500" />
            Connect Jean Memory to Your AI Assistant
          </h1>
          <p className="text-xl text-zinc-400">
            Give your AI assistant access to your personal memory in just a few clicks
          </p>
          <div className="flex justify-center gap-2">
            <Badge variant="secondary">No Technical Skills Required</Badge>
            <Badge variant="secondary">Works in Minutes</Badge>
          </div>
        </div>

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

        {/* Easy Setup */}
        <div className="grid md:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <img src="/images/claude-icon.png" alt="Claude" className="h-6 w-6" onError={(e) => {
                  e.currentTarget.style.display = 'none';
                }} />
                Claude Desktop Users
              </CardTitle>
              <CardDescription>
                If you use Claude Desktop on your computer
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="text-sm space-y-2">
                <p>1. Open Claude Desktop</p>
                <p>2. Look for "Jean Memory" in the tools menu</p>
                <p>3. Start talking to your AI naturally!</p>
              </div>
              <Button className="w-full" asChild>
                <a href="https://claude.ai/download" target="_blank" rel="noopener noreferrer">
                  Get Claude Desktop <ExternalLink className="h-4 w-4 ml-2" />
                </a>
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <img src="/images/cursor-icon.png" alt="Cursor" className="h-6 w-6" onError={(e) => {
                  e.currentTarget.style.display = 'none';
                }} />
                Cursor IDE Users
              </CardTitle>
              <CardDescription>
                If you use Cursor for coding
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="text-sm space-y-2">
                <p>1. Open Cursor IDE</p>
                <p>2. Look for "Jean Memory" in the AI chat</p>
                <p>3. Start having smarter coding conversations!</p>
              </div>
              <Button className="w-full" asChild>
                <a href="https://cursor.sh" target="_blank" rel="noopener noreferrer">
                  Get Cursor IDE <ExternalLink className="h-4 w-4 ml-2" />
                </a>
              </Button>
            </CardContent>
          </Card>
        </div>

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

        {/* Support */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MessageCircle className="h-5 w-5" />
              Need Help?
            </CardTitle>
            <CardDescription>
              Can't find Jean Memory in your AI assistant? Having trouble? We're here to help!
            </CardDescription>
          </CardHeader>
          <CardContent>
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
            <strong>Ready to get started?</strong> Download Claude Desktop or Cursor IDE above, and Jean Memory will be waiting for you!
          </AlertDescription>
        </Alert>
      </div>
    </div>
  );
} 