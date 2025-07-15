"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Check, Star, ArrowRight, BrainCircuit, Key, Tags, Zap, MessageSquareText } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import ParticleNetwork from "@/components/landing/ParticleNetwork";
import { useAuth } from "@/contexts/AuthContext";
import { Badge } from "@/components/ui/badge";
import { ProtectedRoute } from "@/components/ProtectedRoute";

const proFeatures = [
  {
    icon: <MessageSquareText className="w-5 h-5 text-purple-400" />,
    title: "Text Your Memory Anywhere",
    description: "Instantly save memories or ask questions. Your AI assistant works wherever you are, no app required.",
  },
  {
    icon: <Key className="w-5 h-5 text-purple-400" />,
    title: "API Access for Your Apps",
    description: "Connect to all your favorite tools, agents, and workflows. Build consistent memory kingdom across every application you use.",
  },
  {
    icon: <BrainCircuit className="w-5 h-5 text-purple-400" />,
    title: "Discover Hidden Connections",
    description: "Our graph memory reveals surprising relationships between your thoughts, projects, and experiences that you never noticed before.",
  },
  {
    icon: <Tags className="w-5 h-5 text-purple-400" />,
    title: "Advanced Organization",
    description: "Tag, filter, and organize your memories with precision. Find exactly what you need in seconds, not minutes.",
  },
];

export default function ProPage() {
  const { user } = useAuth();

  return (
    <ProtectedRoute>
      <div className="relative min-h-screen bg-background text-foreground">
        <div className="absolute inset-0 z-0 h-full w-full">
          <ParticleNetwork id="pro-particles" className="h-full w-full" interactive={true} particleCount={80} />
        </div>
        <div className="absolute inset-0 bg-gradient-to-b from-purple-900/10 via-background/50 to-background z-5" />

        <div className="relative z-10 container mx-auto px-4 py-16 md:py-24 max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-center mb-12"
          >
            <Badge variant="secondary" className="text-purple-400 border-purple-500/20 mb-4">
              <Star className="w-4 h-4 mr-2 text-purple-500" />
              Go Pro
            </Badge>
            
            <h1 className="text-4xl md:text-5xl font-bold mb-4">
              Build Your Memory Kingdom
            </h1>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              Create a consistent, intelligent memory that works across all your apps, devices, and conversations. Text, connect, and discover like never before.
            </p>
          </motion.div>

          <div className="grid md:grid-cols-5 gap-8 items-start">
            {/* Free Tier */}
            <motion.div
              className="md:col-span-2"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
            >
              <Card className="h-full bg-background/30 backdrop-blur-lg">
                <CardHeader>
                  <CardTitle className="text-2xl">Free</CardTitle>
                  <CardDescription>
                    For individuals getting started with personal memory.
                  </CardDescription>
                  <div className="flex items-baseline gap-1 pt-2">
                    <span className="text-3xl font-bold">$0</span>
                    <span className="text-muted-foreground">/ forever</span>
                  </div>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-3 text-sm">
                    <li className="flex items-center gap-3"><Check className="w-4 h-4 text-green-500" /> Unified memory across apps</li>
                    <li className="flex items-center gap-3"><Check className="w-4 h-4 text-green-500" /> Unlimited memory storage</li>
                    <li className="flex items-center gap-3"><Check className="w-4 h-4 text-green-500" /> Standard search</li>
                    <li className="flex items-center gap-3"><Check className="w-4 h-4 text-green-500" /> Your data is always yours</li>
                  </ul>
                  <Button 
                    className="w-full mt-6" 
                    variant="outline"
                    asChild
                  >
                    <Link href={user ? "/dashboard" : "/auth"}>
                      {user ? "Your Dashboard" : "Get Started"}
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            </motion.div>

            {/* Pro Tier */}
            <motion.div
              className="md:col-span-3"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 0.4 }}
            >
              <Card className="h-full border-purple-500/50 bg-gradient-to-br from-purple-950/20 via-background/30 to-background/30 backdrop-blur-lg shadow-2xl shadow-purple-500/10">
                <CardHeader>
                  <CardTitle className="text-2xl flex items-center gap-2">
                    Pro
                    <Badge className="bg-purple-600 text-white">Recommended</Badge>
                  </CardTitle>
                  <CardDescription>
                    For creators building their personal memory kingdom across all apps and devices.
                  </CardDescription>
                  <div className="flex items-baseline gap-1 pt-2">
                    <span className="text-4xl font-bold">$19</span>
                    <span className="text-muted-foreground">/ month</span>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {proFeatures.map((feature, index) => (
                      <div key={index} className="flex items-start gap-4">
                        <div className="flex-shrink-0 mt-1">{feature.icon}</div>
                        <div>
                          <h4 className="font-semibold">{feature.title}</h4>
                          <p className="text-sm text-muted-foreground">{feature.description}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                  <Button 
                    className="w-full mt-8 bg-purple-600 hover:bg-purple-700 text-white text-lg py-6" 
                    asChild
                  >
                    <a 
                      href="https://buy.stripe.com/8x214n2K0cmVadx3pIabK01" 
                      target="_blank" 
                      rel="noopener noreferrer"
                    >
                      Upgrade and Unlock Pro
                      <ArrowRight className="w-5 h-5 ml-2" />
                    </a>
                  </Button>
                </CardContent>
              </Card>
            </motion.div>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.6 }}
            className="text-center mt-16"
          >
            <div className="max-w-2xl mx-auto">
              <h3 className="text-xl font-semibold mb-4">Need More?</h3>
              <p className="text-muted-foreground mb-6">
                We offer bespoke Enterprise plans for teams that require custom solutions, white-glove support, and dedicated infrastructure.
              </p>
              <Button variant="ghost" asChild>
                <a href="mailto:jonathan@jeantechnologies.com?subject=Enterprise%20Inquiry">
                  Contact Founder for Enterprise Solutions
                  <ArrowRight className="w-4 h-4 ml-2" />
                </a>
              </Button>
            </div>
          </motion.div>
        </div>
      </div>
    </ProtectedRoute>
  );
} 