# Voice Assistant Application Setup Guide

## Overview

This is a **dual-agent AI voice assistant** application that allows you to interact with two different voice AI providers:

1. **ElevenLabs** - High-quality text-to-speech with Claude AI for processing
2. **QWen 3 Omni** - Alibaba's real-time multimodal voice AI with emotional expression capabilities

## Features

- **Toggle Between Two AI Agents**: Switch seamlessly between ElevenLabs and QWen 3 Omni
- **Real-time Voice Interaction**: Push-to-talk interface with live transcription
- **Animated Voice Orb**: Visual feedback during conversations
- **Chat History**: See the full conversation transcript
- **MCP Integration**: Extensible with Model Context Protocol servers
- **Memory Integration**: Persistent conversation memory via Mem0

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (Next.js)                 │
│  ┌──────────────┐  ┌─────────────────────────────┐ │
│  │ Voice Toggle │  │    VoiceAssistant Component │ │
│  │  Component   │  │                             │ │
│  └──────────────┘  └─────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
                         │ WebSocket
                         ▼
┌─────────────────────────────────────────────────────┐
│             Backend (Node.js/TypeScript)             │
│  ┌──────────────────────────────────────────────┐  │
│  │          WebSocket Handler                    │  │
│  │                                               │  │
│  │  ┌────────────────┐  ┌──────────────────┐   │  │
│  │  │  ElevenLabs    │  │   QWen 3 Omni    │   │  │
│  │  │   Pipeline     │  │    Provider      │   │  │
│  │  │                │  │                  │   │  │
│  │  │ • Whisper STT  │  │ • Native ASR     │   │  │
│  │  │ • Claude LLM   │  │ • QWen LLM       │   │  │
│  │  │ • ElevenLabs   │  │ • Emotional TTS  │   │  │
│  │  │   TTS          │  │                  │   │  │
│  │  └────────────────┘  └──────────────────┘   │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## Prerequisites

- Node.js 20+ and npm/yarn/pnpm
- API Keys:
  - Anthropic (Claude)
  - OpenAI (Whisper STT)
  - ElevenLabs
  - Alibaba DashScope (QWen)
  - Mem0
  - Tavily (optional)

## Installation

### 1. Clone and Install Dependencies

```bash
cd voice-app

# Install backend dependencies
cd backend
npm install

# Install frontend dependencies
cd ../frontend
npm install
```

### 2. Configure Environment Variables

The `.env` file has been created with your API keys. Verify the configuration:

```bash
cat voice-app/.env
```

**Important Environment Variables:**

```env
# API Keys
ANTHROPIC_API_KEY=your_claude_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
DASHSCOPE_API_KEY=your_dashscope_api_key_here
MEM0_API_KEY=your_mem0_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here

# Azure AI Speech (optional - for future integration)
AZURE_SPEECH_KEY=your_azure_speech_key_here
AZURE_SPEECH_REGION=eastus

# Voice Configuration - Default Agent
DEFAULT_VOICE_AGENT=elevenlabs

# ElevenLabs Configuration
ELEVENLABS_VOICE_ID=JBFqnCBsd6RMkjVDRZzb
ELEVENLABS_MODEL_ID=eleven_multilingual_v2

# QWen 3 Omni Configuration
QWEN_OMNI_MODEL=qwen3-omni-flash-realtime
QWEN_OMNI_VOICE=Cherry
QWEN_OMNI_ENDPOINT=wss://dashscope.aliyuncs.com/api-ws/v1/realtime
```

### 3. Start the Application

**Option A: Development Mode (Recommended)**

In two separate terminals:

```bash
# Terminal 1: Start Backend
cd voice-app/backend
npm run dev

# Terminal 2: Start Frontend
cd voice-app/frontend
npm run dev
```

**Option B: Docker Compose**

```bash
cd voice-app
docker-compose up
```

### 4. Access the Application

Open your browser and navigate to:
- Frontend: `http://localhost:3000`
- Backend WebSocket: `ws://localhost:8080`

## Usage

### Switching Between Voice Agents

1. **ElevenLabs Agent** (Blue Button):
   - Uses OpenAI Whisper for speech recognition
   - Claude AI for conversation intelligence
   - ElevenLabs for high-quality text-to-speech
   - Best for: Natural conversations, general assistance

2. **QWen 3 Omni Agent** (Purple Button):
   - Uses QWen's native real-time ASR
   - QWen 3 Omni LLM for processing
   - Emotional voice synthesis
   - Best for: Expressive responses, multilingual support, real-time interaction

### Push-to-Talk Interface

1. Press and hold the microphone button
2. Speak your message
3. Release the button to process
4. Wait for the AI response with audio playback

### Voice Agent Selection

- Toggle is located in the header next to the connection status
- Can only switch when the assistant is idle (not processing)
- Selection persists for your session

## QWen 3 Omni Features

### Supported Languages
- Mandarin Chinese (multiple dialects)
- English
- Spanish
- Russian
- Italian
- French
- Korean
- Japanese
- German
- Portuguese

### Available Voices

**QWen3-TTS Voices:**
- **Cherry**: Cheerful, friendly young woman
- **Ethan**: Standard Mandarin with slight northern accent
- **Jennifer**: Premium cinematic American English female voice
- **Ryan**: Rhythmic, dramatic voice with tension
- Plus 13+ other voices including regional Chinese dialects

### Emotional Expression

QWen 3 Omni automatically adjusts:
- Tone and prosody
- Emotional inflections
- Pacing based on context
- Natural emphasis patterns

## MCP (Model Context Protocol) Integration

The application supports MCP servers for extended capabilities:

### Pre-configured MCP Servers:

1. **GitHub** - Repository management
2. **Brave Search** - Web search capabilities
3. **Mem0** - Persistent memory across conversations
4. **Playwright** - Web automation
5. **Chrome DevTools** - Browser automation
6. **Desktop Commander** - System interactions
7. **Shadcn** - UI component generation
8. **21st Magic** - Component inspiration

### Adding More MCP Servers

Edit `.env` and add your MCP server configurations following the existing pattern.

## Troubleshooting

### WebSocket Connection Issues

```bash
# Check if backend is running
curl http://localhost:8080

# Check logs
cd voice-app/backend
npm run dev
```

### Audio Not Playing

1. Ensure browser has microphone permissions
2. Check audio output device settings
3. Verify API keys are correct
4. Check browser console for errors

### QWen 3 Omni Connection Errors

1. Verify DASHSCOPE_API_KEY is correct
2. Check network connectivity to Alibaba Cloud
3. Ensure you're using the correct endpoint for your region:
   - China: `wss://dashscope.aliyuncs.com/api-ws/v1/realtime`
   - International: `wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime`

### ElevenLabs Rate Limits

- Check your ElevenLabs plan limits
- Implement rate limiting if needed
- Consider upgrading your plan for higher usage

## API Rate Limits

### ElevenLabs
- Free tier: 10,000 characters/month
- Starter: 30,000 characters/month
- Pro: 100,000 characters/month

### QWen/DashScope
- Check your Alibaba Cloud console for current limits
- Pricing based on tokens and audio duration

### OpenAI (Whisper)
- $0.006 per minute of audio

## Development

### Backend Structure

```
backend/
├── src/
│   ├── voice/
│   │   ├── pipeline.ts      # ElevenLabs pipeline
│   │   ├── qwen-omni.ts     # QWen Omni provider
│   │   ├── stt.ts           # Whisper STT
│   │   └── tts.ts           # ElevenLabs TTS
│   ├── websocket/
│   │   ├── server.ts        # WebSocket server
│   │   └── handlers.ts      # Message handlers
│   ├── llm/
│   │   └── claude.ts        # Claude integration
│   ├── mcp/
│   │   ├── client.ts        # MCP client
│   │   └── servers.ts       # MCP server configs
│   └── types/
│       └── index.ts         # TypeScript types
```

### Frontend Structure

```
frontend/
├── components/
│   ├── VoiceAssistant.tsx      # Main component
│   ├── VoiceAgentToggle.tsx    # Agent toggle UI
│   ├── AnimatedOrb.tsx         # Visual feedback
│   └── ChatUI.tsx              # Message display
├── hooks/
│   ├── useWebSocket.ts         # WebSocket hook
│   └── useAudio.ts             # Audio recording/playback
└── lib/
    └── types.ts                # TypeScript types
```

## Contributing

When adding new features:

1. Update types in both `backend/src/types/index.ts` and `frontend/lib/types.ts`
2. Add tests for new functionality
3. Update this README with new features
4. Ensure backward compatibility

## Security Considerations

- Never commit `.env` files with real API keys
- Use environment variables for all sensitive data
- Implement rate limiting in production
- Add authentication for production deployments
- Use HTTPS/WSS in production

## License

MIT License - See LICENSE file for details

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review backend logs
3. Check browser console
4. Open an issue on the repository

---

**Note**: This application uses real-time voice AI and may incur costs based on your API usage. Monitor your usage across all services to avoid unexpected charges.
