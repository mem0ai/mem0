"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Check, Star, Zap, Shield, Globe, Key, ArrowRight, Brain, Network, Database, Sparkles } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import ParticleNetwork from "@/components/landing/ParticleNetwork";
import { useAuth } from "@/contexts/AuthContext";
import { Badge } from "@/components/ui/badge";

export default function ProPage() {
  const { user } = useAuth();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const features = {
    free: [
      "Memory across Claude Desktop",
      "Memory across Cursor", 
      "Memory across most AI apps",
      "Basic search functionality",
      "Unlimited memories",
      "Your data stays yours forever",
      "Standard support"
    ],
    pro: [
      "Everything in Free",
      "Full API access with authentication",
      "Advanced metadata tagging & filtering", 
      "ChatGPT Enterprise Deep Research",
      "High-performance vector search",
      "Priority support",
      "Advanced analytics & insights"
    ],
    enterprise: [
      "Everything in Pro",
      "Custom API/SDK development",
      "White-label solutions",
      "Advanced authentication systems",
      "Custom data pipelines",
      "Dedicated infrastructure",
      "Shared memory across teams",
      "Direct founder support"
    ]
  };

  const integrations = [
    { name: "Claude Desktop", icon: Brain, status: "free" },
    { name: "Cursor", icon: Database, status: "free" },
    { name: "API Access", icon: Key, status: "pro" },
    { name: "ChatGPT Enterprise", icon: Sparkles, status: "pro" },
    { name: "Custom SDK", icon: Network, status: "enterprise" },
    { name: "White-label API", icon: Zap, status: "enterprise" }
  ];

  return (
    <div className="relative min-h-screen bg-background text-foreground">
      {/* Background Animation */}
      <div className="absolute inset-0 z-0 h-full w-full">
        <ParticleNetwork id="pro-particles" className="h-full w-full" interactive={true} particleCount={120} />
      </div>

      {/* Gradient Overlays */}
      <div className="absolute inset-0 bg-gradient-to-b from-purple-950/20 via-transparent to-zinc-950/40 z-5" />
      <div className="absolute inset-0 bg-gradient-radial from-transparent via-background/50 to-background z-5" />

      {/* Main Content */}
      <div className="relative z-10 container mx-auto px-4 py-16 max-w-6xl">
        {/* Hero Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="text-center mb-16"
        >
          <div className="flex items-center justify-center gap-2 mb-4">
            <Star className="w-6 h-6 text-purple-500" />
            <Badge variant="secondary" className="text-purple-400 border-purple-500/20">
              Jean Memory Pro
            </Badge>
          </div>
          
          <h1 className="text-5xl sm:text-6xl font-bold mb-6 bg-gradient-to-b from-foreground to-muted-foreground bg-clip-text text-transparent">
            Unlock the Full Power
          </h1>
          <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
            Enterprise-grade memory infrastructure for your AI applications. 
            Start free, upgrade when you need advanced features.
          </p>
        </motion.div>

                 {/* Pricing Cards */}
         <div className="grid md:grid-cols-3 gap-8 mb-16">
          {/* Free Tier */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
          >
            <Card className="relative h-full border-border/50 bg-card/30 backdrop-blur-lg">
              <CardHeader className="pb-6">
                <div className="flex items-center justify-between mb-2">
                  <CardTitle className="text-2xl">Free</CardTitle>
                  <Badge variant="secondary" className="text-green-400 border-green-500/20">
                    Always Free
                  </Badge>
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="text-4xl font-bold">$0</span>
                  <span className="text-muted-foreground">/month</span>
                </div>
                                 <CardDescription className="text-muted-foreground">
                   Perfect for individual users. Free forever, your data is always yours.
                 </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <ul className="space-y-3">
                  {features.free.map((feature, index) => (
                    <li key={index} className="flex items-center gap-3">
                      <Check className="w-4 h-4 text-green-500 flex-shrink-0" />
                      <span className="text-sm">{feature}</span>
                    </li>
                  ))}
                </ul>
                <Button 
                  className="w-full" 
                  variant="outline"
                  asChild
                >
                  <Link href={user ? "/dashboard-new" : "/auth"}>
                    {user ? "Go to Dashboard" : "Get Started Free"}
                  </Link>
                </Button>
              </CardContent>
            </Card>
          </motion.div>

          {/* Pro Tier */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
          >
            <Card className="relative h-full border-purple-500/30 bg-gradient-to-b from-purple-950/20 to-card/30 backdrop-blur-lg">
              <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
                <Badge className="bg-purple-600 text-white">
                  <Star className="w-3 h-3 mr-1" />
                  Most Popular
                </Badge>
              </div>
              
              <CardHeader className="pb-6">
                                 <div className="flex items-center justify-between mb-2">
                   <CardTitle className="text-2xl">Pro</CardTitle>
                 </div>
                                 <div className="flex items-baseline gap-1">
                   <span className="text-4xl font-bold">$19</span>
                   <span className="text-muted-foreground">/month</span>
                 </div>
                 <CardDescription className="text-muted-foreground">
                   Pro versions of your favorite tools with advanced memory features
                 </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <ul className="space-y-3">
                  {features.pro.map((feature, index) => (
                    <li key={index} className="flex items-center gap-3">
                      <Check className="w-4 h-4 text-purple-400 flex-shrink-0" />
                      <span className="text-sm">{feature}</span>
                    </li>
                  ))}
                </ul>
                                 <Button 
                   className="w-full bg-purple-600 hover:bg-purple-700 text-white" 
                   asChild
                 >
                   <a 
                     href="https://buy.stripe.com/8x214n2K0cmVadx3pIabK01" 
                     target="_blank" 
                     rel="noopener noreferrer"
                   >
                     Upgrade to Pro
                     <ArrowRight className="w-4 h-4 ml-2" />
                   </a>
                 </Button>
              </CardContent>
            </Card>
                     </motion.div>

           {/* Enterprise Tier */}
           <motion.div
             initial={{ opacity: 0, x: 20 }}
             animate={{ opacity: 1, x: 0 }}
             transition={{ duration: 0.6, delay: 0.6 }}
           >
             <Card className="relative h-full border-zinc-500/30 bg-gradient-to-b from-zinc-900/20 to-card/30 backdrop-blur-lg">
               <CardHeader className="pb-6">
                 <div className="flex items-center justify-between mb-2">
                   <CardTitle className="text-2xl">Enterprise</CardTitle>
                   <Badge className="bg-zinc-700 text-white">
                     Bespoke
                   </Badge>
                 </div>
                 <div className="flex items-baseline gap-1">
                   <span className="text-2xl font-bold">Custom</span>
                   <span className="text-muted-foreground">pricing</span>
                 </div>
                 <CardDescription className="text-muted-foreground">
                   Custom API/SDK solutions and enterprise infrastructure
                 </CardDescription>
               </CardHeader>
               <CardContent className="space-y-6">
                 <ul className="space-y-3">
                   {features.enterprise.map((feature, index) => (
                     <li key={index} className="flex items-center gap-3">
                       <Check className="w-4 h-4 text-zinc-400 flex-shrink-0" />
                       <span className="text-sm">{feature}</span>
                     </li>
                   ))}
                 </ul>
                 <Button 
                   className="w-full bg-zinc-700 hover:bg-zinc-600 text-white" 
                   asChild
                 >
                   <a 
                     href="mailto:jonathan@jeantechnologies.com?subject=Enterprise%20Inquiry&body=Hi%20Jonathan,%0A%0AI'm%20interested%20in%20Jean%20Memory%20Enterprise%20solutions.%0A%0APlease%20tell%20me%20more%20about:"
                     target="_blank"
                     rel="noopener noreferrer"
                   >
                     Email Founder
                     <ArrowRight className="w-4 h-4 ml-2" />
                   </a>
                 </Button>
               </CardContent>
             </Card>
           </motion.div>
         </div>

        {/* Integration Grid */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.6 }}
          className="mb-16"
        >
          <h2 className="text-3xl font-bold text-center mb-8">What's Included</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {integrations.map((integration, index) => (
              <motion.div
                key={integration.name}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.3, delay: 0.7 + index * 0.1 }}
              >
                                 <Card className={`text-center p-4 h-full ${
                   integration.status === 'pro' 
                     ? 'border-purple-500/30 bg-purple-950/10' 
                     : integration.status === 'enterprise'
                     ? 'border-zinc-500/30 bg-zinc-900/10'
                     : 'border-border/50 bg-card/30'
                 } backdrop-blur-lg`}>
                   <CardContent className="p-0 space-y-3">
                     <div className={`w-12 h-12 rounded-full flex items-center justify-center mx-auto ${
                       integration.status === 'pro' 
                         ? 'bg-purple-500/20 text-purple-400' 
                         : integration.status === 'enterprise'
                         ? 'bg-zinc-500/20 text-zinc-400'
                         : 'bg-green-500/20 text-green-400'
                     }`}>
                       <integration.icon className="w-6 h-6" />
                     </div>
                     <div>
                       <h3 className="font-semibold text-sm">{integration.name}</h3>
                       <Badge 
                         variant="secondary" 
                         className={`text-xs mt-1 ${
                           integration.status === 'pro' 
                             ? 'text-purple-400 border-purple-500/20' 
                             : integration.status === 'enterprise'
                             ? 'text-zinc-400 border-zinc-500/20'
                             : 'text-green-400 border-green-500/20'
                         }`}
                       >
                         {integration.status === 'pro' ? 'Pro Only' : integration.status === 'enterprise' ? 'Enterprise' : 'Free'}
                       </Badge>
                     </div>
                   </CardContent>
                 </Card>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* FAQ Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.8 }}
          className="max-w-3xl mx-auto"
        >
          <h2 className="text-3xl font-bold text-center mb-8">Frequently Asked Questions</h2>
          <div className="space-y-6">
            <Card className="border-border/50 bg-card/30 backdrop-blur-lg">
              <CardHeader>
                <CardTitle className="text-lg">What happens to my free features?</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground">
                  All free features remain free forever. Pro adds advanced capabilities on top of your existing setup.
                </p>
              </CardContent>
            </Card>

                         <Card className="border-border/50 bg-card/30 backdrop-blur-lg">
               <CardHeader>
                 <CardTitle className="text-lg">Do I need ChatGPT Enterprise?</CardTitle>
               </CardHeader>
               <CardContent>
                 <p className="text-muted-foreground">
                   The ChatGPT Deep Research integration requires a ChatGPT Enterprise account, but all other Pro features work without it.
                 </p>
               </CardContent>
             </Card>

             <Card className="border-border/50 bg-card/30 backdrop-blur-lg">
               <CardHeader>
                 <CardTitle className="text-lg">What's included in Enterprise?</CardTitle>
               </CardHeader>
               <CardContent>
                 <p className="text-muted-foreground">
                   Enterprise includes custom API/SDK development, white-label solutions, dedicated infrastructure, and direct access to the founder for bespoke memory solutions.
                 </p>
               </CardContent>
             </Card>

            <Card className="border-border/50 bg-card/30 backdrop-blur-lg">
              <CardHeader>
                <CardTitle className="text-lg">Can I cancel anytime?</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground">
                  Yes, you can cancel your Pro subscription at any time. Your account will revert to the free tier at the end of your billing period.
                </p>
              </CardContent>
            </Card>
          </div>
        </motion.div>

        {/* CTA Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 1.0 }}
          className="text-center mt-16"
        >
          <Card className="border-purple-500/30 bg-gradient-to-b from-purple-950/20 to-card/30 backdrop-blur-lg p-8">
            <CardContent className="space-y-6">
              <h2 className="text-3xl font-bold">Ready to unlock enterprise-grade memory?</h2>
              <p className="text-muted-foreground max-w-xl mx-auto">
                Join developers and teams who trust Jean Memory for their most critical AI applications.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Button variant="outline" size="lg" asChild>
                  <Link href={user ? "/dashboard-new" : "/auth"}>
                    {user ? "Dashboard" : "Start Free"}
                  </Link>
                </Button>
                                <Button size="lg" className="bg-purple-600 hover:bg-purple-700 text-white" asChild>
                  <a 
                    href="https://buy.stripe.com/8x214n2K0cmVadx3pIabK01" 
                    target="_blank" 
                    rel="noopener noreferrer"
                  >
                    <Star className="w-4 h-4 mr-2" />
                    Upgrade to Pro
                  </a>
                </Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
} 