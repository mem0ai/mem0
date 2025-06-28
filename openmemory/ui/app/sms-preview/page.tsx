"use client";

import { motion } from "framer-motion";
import { Phone, Check, Star } from "lucide-react";

export default function SmsPreviewPage() {
  return (
    <div className="relative min-h-screen bg-black text-white overflow-hidden flex items-center justify-center p-4">
      {/* Gradient Overlays */}
      <div className="absolute inset-0 bg-gradient-to-b from-blue-950/60 via-transparent to-slate-950/60" />
      <div className="absolute inset-0 bg-gradient-radial from-transparent via-black/80 to-black" />

      {/* Main Content */}
      <div className="relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="text-center max-w-md mx-auto w-full bg-slate-900/80 backdrop-blur-sm border border-slate-700 rounded-2xl p-8 shadow-2xl shadow-blue-500/10"
        >
          {/* Icon */}
          <motion.div
            initial={{ scale: 0.5, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="mx-auto w-16 h-16 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center mb-6"
          >
            <Phone className="w-8 h-8 text-blue-400" />
          </motion.div>

          {/* Title and Pro Badge */}
          <div className="flex items-center justify-center gap-3 mb-2">
            <motion.h1
              className="text-2xl font-bold text-slate-100 tracking-tight"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
            >
              Connect SMS to Jean Memory
            </motion.h1>
            <motion.div
              className="bg-purple-500/20 text-purple-300 text-xs font-semibold px-2.5 py-1 rounded-full flex items-center gap-1"
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
            className="text-sm text-slate-400 mb-8"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.4 }}
          >
            Add your phone number to interact with your memories via text message.
          </motion.p>
          
          {/* Mockup Form */}
          <div className="space-y-2 mb-4">
            <label htmlFor="phone-number" className="text-left block text-sm font-medium text-slate-300 mb-1">Phone Number *</label>
            <div className="relative">
              <input
                id="phone-number"
                type="tel"
                placeholder="(555) 123-4567"
                className="w-full bg-slate-800/50 border border-slate-600 rounded-lg pl-4 pr-4 py-2.5 text-white placeholder-slate-500 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                disabled
              />
            </div>
          </div>
          
          {/* Consent Text */}
          <p className="text-xs text-slate-500 mb-6">
            US phone numbers only. By providing your phone number, you agree to receive text messages from Jean Memory for account verification and to interact with your memory assistant. Message & data rates may apply.
          </p>
          
          {/* How to Use Box */}
          <motion.div
            className="mb-8 text-sm text-slate-400 text-left bg-slate-800/50 p-4 rounded-lg border border-slate-700"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.6 }}
          >
            <p className="font-bold text-slate-200 mb-2">How to Use Jean Memory SMS:</p>
            <ul className="list-disc list-inside space-y-1 text-slate-400 text-xs">
                <li>"Remember to pick up groceries after work"</li>
                <li>"What were the main points from the meeting yesterday?"</li>
                <li>"Show my recent thoughts on the new project"</li>
                <li>Text "help" anytime for more examples.</li>
            </ul>
          </motion.div>

          {/* Action Buttons */}
          <div className="grid grid-cols-2 gap-3">
            <button
              className="w-full inline-flex items-center justify-center px-4 py-2.5 font-semibold rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition-all duration-300 shadow-lg"
              disabled
            >
              Cancel
            </button>
            <button
              className="w-full inline-flex items-center justify-center px-4 py-2.5 font-semibold rounded-lg bg-slate-200 text-slate-900 transition-all duration-300 shadow-lg"
              disabled
            >
              Send Code
            </button>
          </div>

          <p className="text-xs text-slate-600 mt-8">
              This is a static mockup page for Twilio campaign verification purposes.
          </p>
        </motion.div>
      </div>
    </div>
  );
} 