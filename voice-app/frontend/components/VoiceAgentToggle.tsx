'use client';

import { VoiceAgent } from '@/lib/types';
import { cn } from '@/lib/utils';
import { Zap, Sparkles } from 'lucide-react';

interface VoiceAgentToggleProps {
  currentAgent: VoiceAgent;
  onAgentChange: (agent: VoiceAgent) => void;
  disabled?: boolean;
}

export function VoiceAgentToggle({ currentAgent, onAgentChange, disabled }: VoiceAgentToggleProps) {
  return (
    <div className="flex items-center gap-2 bg-gray-800 rounded-lg p-1">
      <button
        onClick={() => onAgentChange('elevenlabs')}
        disabled={disabled}
        className={cn(
          'flex items-center gap-2 px-4 py-2 rounded-md transition-all duration-200',
          'text-sm font-medium',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          currentAgent === 'elevenlabs'
            ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/50'
            : 'text-gray-400 hover:text-white hover:bg-gray-700'
        )}
      >
        <Zap className="w-4 h-4" />
        <span>ElevenLabs</span>
      </button>

      <button
        onClick={() => onAgentChange('qwen-omni')}
        disabled={disabled}
        className={cn(
          'flex items-center gap-2 px-4 py-2 rounded-md transition-all duration-200',
          'text-sm font-medium',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          currentAgent === 'qwen-omni'
            ? 'bg-purple-600 text-white shadow-lg shadow-purple-600/50'
            : 'text-gray-400 hover:text-white hover:bg-gray-700'
        )}
      >
        <Sparkles className="w-4 h-4" />
        <span>QWen 3 Omni</span>
      </button>
    </div>
  );
}
