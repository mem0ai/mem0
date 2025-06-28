"use client";

import { motion } from "framer-motion";
import { Phone, Check } from "lucide-react";

export default function SmsPreviewPage() {
  return (
    <div className="relative min-h-screen bg-black text-white overflow-hidden flex items-center justify-center">
      {/* Gradient Overlays */}
      <div className="absolute inset-0 bg-gradient-to-b from-blue-950/60 via-transparent to-slate-950/60" />
      <div className="absolute inset-0 bg-gradient-radial from-transparent via-black/80 to-black" />

      {/* Main Content */}
      <div className="relative z-10 flex flex-col items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="text-center max-w-lg mx-auto w-full bg-black/50 backdrop-blur-sm border border-gray-800 rounded-lg p-8"
        >
          {/* Title */}
          <motion.h1
            className="text-3xl font-semibold mb-4 text-gray-200 tracking-tight"
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            SMS Integration Preview
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            className="text-md text-gray-400 mb-8"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.4 }}
          >
            This page is a mockup for Twilio A2P 10DLC verification.
          </motion.p>
          
          {/* Mockup Form */}
          <div className="space-y-4">
            <div className="relative">
              <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500" />
              <input
                type="tel"
                placeholder="+1 (555) 123-4567"
                className="w-full bg-gray-900/50 border border-gray-700 rounded-md pl-10 pr-4 py-3 text-white placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                disabled
              />
            </div>
            <button
              className="w-full inline-flex items-center justify-center gap-2 px-6 py-3 font-bold rounded-md bg-gray-700 text-gray-300 transition-all duration-300 shadow-lg"
              disabled
            >
              Send Verification Code
            </button>
          </div>

          {/* Consent Text */}
          <motion.div
            className="mt-8 text-xs text-gray-500 text-left bg-gray-900/50 p-4 rounded-lg border border-gray-800"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.6 }}
          >
            <p className="font-bold text-gray-400 mb-2">Consent Language:</p>
            <p>
              By providing your phone number, you agree to receive text messages from Jean Memory for account verification and to interact with your memory assistant. Message and data rates may apply. Message frequency varies based on your usage. Reply STOP to cancel, HELP for help.
            </p>
          </motion.div>
        </motion.div>
      </div>
    </div>
  );
} 