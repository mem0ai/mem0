"use client";

import ParticleNetwork from "@/components/landing/ParticleNetwork";
import { motion } from "framer-motion";

export default function PrivacyPage() {
  return (
    <div className="relative min-h-screen bg-background text-foreground">
      {/* Background Animation */}
      <div className="absolute inset-0 z-0 h-full w-full">
        <ParticleNetwork id="privacy-particles" className="h-full w-full" interactive={false} particleCount={50} />
      </div>

      {/* Main Content */}
      <div className="relative z-10 container mx-auto px-4 py-16 max-w-3xl">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="p-8 md:p-12"
        >
          <div className="text-center mb-16">
            <h1 className="text-5xl md:text-6xl font-bold tracking-tight mb-4">
              Your Memory
            </h1>
            <p className="text-xl text-muted-foreground">
              Personal context layer for all of your software.
            </p>
          </div>

          <div className="space-y-12 text-lg leading-relaxed prose dark:prose-invert mx-auto">
            <section>
              <p>Your context is a projection of your mind. AI now understands this projection deeply. We believe that makes it important to get this infrastructure right.<a href="https://jonathanpolitzki.substack.com/p/general-personal-embeddings" target="_blank" rel="noopener noreferrer" className="no-underline"><sup className="text-primary font-medium ml-1">[1]</sup></a></p>
              <p>We are building a future defined by trust, where we own our context and our context does not own us.</p>
            </section>
            
            <section>
              <h2 className="text-3xl font-bold tracking-tight !mb-6 !mt-12">Our Guiding Principles</h2>
              <p>This is a promise we are building towards. We make every decision based on building trust.</p>
              <ul className="space-y-4">
                <li><strong>Open Source & Self-Hostable.</strong> The entire platform is open source. You can run it on your own hardware for absolute control. Every algorithm is auditable on GitHub, and contributions are welcome.</li>
                <li><strong>A Commitment to Zero-Knowledge.</strong> We are building a future with end-to-end encryption and zero-knowledge proofs. Jean will not see your personal information.</li>
                <li><strong>Radical Portability & The Right to be Forgotten.</strong> No vendor lock-in. Instantly export your data via open standards, or delete it with the guarantee that it is gone. Forever.</li>
                <li><strong>Built for Enterprise-Grade Security.</strong> Our platform is engineered with the principles of leading security and privacy standards, including SOC 2 and GDPR, in mind. We are committed to a roadmap that includes formal certification to provide verifiable trust for all our users.</li>
              </ul>
            </section>
            
            <section className="border-t border-border/50 pt-8 text-sm not-prose">
              <h3 className="font-semibold text-base text-foreground mb-4">References</h3>
              <div className="space-y-3 text-muted-foreground">
                <p id="ref-1" className="flex items-start">
                  <span className="mr-2">[1]</span>
                  <span>Politzki, J. (2024). <a href="https://jonathanpolitzki.substack.com/p/general-personal-embeddings" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline"><em>General Personal Embeddings: A trusted infrastructure for the age of AI</em></a>.</span>
                </p>
              </div>
            </section>

            <section className="!max-w-none not-prose border-t border-border/50 pt-12">
              <h3 className="text-center text-2xl font-bold tracking-tight mb-8">From Our Writings</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-xs">
                <a href="https://jonathanpolitzki.substack.com/p/general-personal-embeddings" target="_blank" rel="noopener noreferrer" className="text-center block p-3 rounded-lg hover:bg-muted/50 transition-colors">
                  <p className="font-semibold text-foreground text-sm mb-1">General Personal Embeddings</p>
                  <p className="text-muted-foreground leading-snug">A trusted infrastructure for the age of AI</p>
                </a>
                <a href="https://jonathanpolitzki.substack.com/p/google-tear-down-this-wall" target="_blank" rel="noopener noreferrer" className="text-center block p-3 rounded-lg hover:bg-muted/50 transition-colors">
                  <p className="font-semibold text-foreground text-sm mb-1">Google, Tear Down This Wall</p>
                  <p className="text-muted-foreground leading-snug">A quick overview of where we are</p>
                </a>
                <a href="https://jonathanpolitzki.substack.com/p/politzkis-law" target="_blank" rel="noopener noreferrer" className="text-center block p-3 rounded-lg hover:bg-muted/50 transition-colors">
                  <p className="font-semibold text-foreground text-sm mb-1">Politzki's Law</p>
                  <p className="text-muted-foreground leading-snug">Maximizing Human Potential in a Likely World</p>
                </a>
                 <a href="https://jonathanpolitzki.substack.com/p/jean-software-for-the-individual" target="_blank" rel="noopener noreferrer" className="text-center block p-3 rounded-lg hover:bg-muted/50 transition-colors">
                  <p className="font-semibold text-foreground text-sm mb-1">Jean - Software for the Individual</p>
                  <p className="text-muted-foreground leading-snug">My Life's Work - Top-Down and Inside-Out</p>
                </a>
                <a href="https://jonathanpolitzki.substack.com/p/b2c-memory-layer" target="_blank" rel="noopener noreferrer" className="text-center block p-3 rounded-lg hover:bg-muted/50 transition-colors">
                  <p className="font-semibold text-foreground text-sm mb-1">B2C Memory Layer</p>
                  <p className="text-muted-foreground leading-snug">Trying something new here</p>
                </a>
                <a href="https://jonathanpolitzki.substack.com/p/jean-memory-the-necessity-of-irreverence" target="_blank" rel="noopener noreferrer" className="text-center block p-3 rounded-lg hover:bg-muted/50 transition-colors">
                  <p className="font-semibold text-foreground text-sm mb-1">Jean Memory</p>
                  <p className="text-muted-foreground leading-snug">The Necessity of Irreverence</p>
                </a>
              </div>
            </section>

            <section className="text-center pt-8">
              <p className="text-muted-foreground not-prose">
                <a href="mailto:contact@jeantechnologies.com" className="hover:text-primary transition-colors"><strong>contact@jeantechnologies.com</strong></a> • <a href="https://github.com/jonathan-politzki/your-memory" target="_blank" rel="noopener noreferrer" className="hover:text-primary transition-colors"><strong>github.com/jonathan-politzki/your-memory</strong></a>
              </p>
            </section>
          </div>
        </motion.div>
      </div>
    </div>
  );
} 