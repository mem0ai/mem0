"use client";

import { motion } from "framer-motion";
import { Phone, Check, Star } from "lucide-react";

export default function SmsPreviewPage() {
  return (
    <div className="relative min-h-screen bg-background text-foreground overflow-hidden flex items-center justify-center p-4">
      {/* Gradient Overlays */}
      <div className="absolute inset-0 bg-gradient-to-b from-blue-950/60 via-transparent to-slate-950/60" />
      <div className="absolute inset-0 bg-gradient-radial from-transparent via-black/80 to-black" />

      {/* Main Content */}
      <div className="relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="text-center max-w-md mx-auto w-full bg-card/80 backdrop-blur-sm border rounded-2xl p-8 shadow-2xl shadow-primary/10"
        >
          {/* Icon */}
          <motion.div
            initial={{ scale: 0.5, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="mx-auto w-16 h-16 rounded-xl bg-muted border flex items-center justify-center mb-6"
          >
            <Phone className="w-8 h-8 text-primary" />
          </motion.div>

          {/* Title and Pro Badge */}
          <div className="flex items-center justify-center gap-3 mb-2">
            <motion.h1
              className="text-2xl font-bold text-card-foreground tracking-tight"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
            >
              Connect SMS to Jean Memory
            </motion.h1>
            <motion.div
              className="bg-primary/20 text-primary text-xs font-semibold px-2.5 py-1 rounded-full flex items-center gap-1"
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.3 }}
            >
              <Star className="w-3 h-3" />
              PRO
            </motion.div>
          </div>

          {/* Subtitle */}
          <motion.p
            className="text-sm text-muted-foreground mb-8"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.4 }}
          >
            Add your phone number to interact with your memories via text message.
          </motion.p>
          
          {/* Mockup Form */}
          <div className="space-y-2 mb-4">
            <label htmlFor="phone-number" className="text-left block text-sm font-medium text-card-foreground mb-1">Phone Number *</label>
            <div className="relative">
              <input
                id="phone-number"
                type="tel"
                placeholder="(555) 123-4567"
                className="w-full bg-muted border rounded-lg pl-4 pr-4 py-2.5 text-foreground placeholder-muted-foreground focus:ring-2 focus:ring-primary focus:border-primary outline-none"
                disabled
              />
            </div>
          </div>
          
          {/* Consent Text */}
          <p className="text-xs text-muted-foreground mb-6">
            US phone numbers only. By providing your phone number, you agree to receive text messages from Jean Memory for account verification and to interact with your memory assistant. Message & data rates may apply.
          </p>
          
          {/* How to Use Box */}
          <motion.div
            className="mb-8 text-sm text-muted-foreground text-left bg-muted p-4 rounded-lg border"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.6 }}
          >
            <p className="font-bold text-card-foreground mb-2">How to Use Jean Memory SMS:</p>
            <ul className="list-disc list-inside space-y-1 text-muted-foreground text-xs">
                <li>"Remember to pick up groceries after work"</li>
                <li>"What were the main points from the meeting yesterday?"</li>
                <li>"Show my recent thoughts on the new project"</li>
                <li>Text "help" anytime for more examples.</li>
            </ul>
          </motion.div>

          {/* Action Buttons */}
          <div className="grid grid-cols-2 gap-3">
            <button
              className="w-full inline-flex items-center justify-center px-4 py-2.5 font-semibold rounded-lg bg-muted text-muted-foreground hover:bg-muted/80 transition-all duration-300 shadow-lg"
              disabled
            >
              Cancel
            </button>
            <button
              className="w-full inline-flex items-center justify-center px-4 py-2.5 font-semibold rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-all duration-300 shadow-lg"
              disabled
            >
              Send Code
            </button>
          </div>

          <p className="text-xs text-muted-foreground mt-8">
              This is a public mockup page for A2P 10DLC campaign verification. <br/>
              Visit <a href="https://jean-memory-ui-virginia.onrender.com/dashboard" className="text-primary hover:underline">Jean Memory Dashboard</a> to connect your phone number.
          </p>
        </motion.div>
      </div>
    </div>
  );
} 